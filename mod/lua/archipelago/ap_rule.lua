-- Archipelago runtime game rule (open campaign, story campaign, survival). Runs on the host only.
--   Game -> client: log lines "[AP] <KIND> <args>" in Documents/The Riftbreaker/exor_logs.txt
--     HELLO <protocol>               rule started (new map or save loaded); a full snapshot follows
--     MODE <open|story|survival>     the game mode detected for this campaign
--     BOUND <session> / MISMATCH <session>
--     CHECKS id,id,... / CHECK id,id done locations (research, builds, story missions)
--     BIOME <name>                   current biome (open campaign arrivals)
--     SURVIVE <seconds>              survival time so far (survival)
--     GOAL <arcology|prime_rift|survival>
--     RECEIVED <index> <item id>
--     EL_DEPOSIT <seq> <resource> <amount> / EL_WITHDRAW <seq> <resource> <amount>   Energy Link requests
--   Client -> game: <game>/archipelago/inbox.lua (polled with loadfile)
--     return { session, connected, player, mode, survival_map, energy_link, energy, items = {...}, labels = {...},
--              grants = { {id, resource, amount}, ... }, tracker = "..." }

require("lua/archipelago/ap_data.lua")

local PROTOCOL        = 3
local INBOX_PATH      = "../archipelago/inbox.lua"   -- relative to bin/, the game's working directory
local POLL_SECONDS    = 2.0
local RESYNC_SECONDS  = 30.0
local MESSAGE_SECONDS = 5.0
local KEY_APPLIED     = "archipelago.items_applied"
local KEY_SESSION     = "archipelago.session"
local KEY_DONE        = "archipelago.done."
local KEY_SURVIVAL    = "archipelago.survival_seconds"
local KEY_EL_SEQ      = "archipelago.el_seq"
local KEY_EL_GRANT    = "archipelago.el_grant"
local HUD_STATUS      = "archipelago_status"
local HUD_ITEM        = "archipelago_item"

local GOALS = {
    { flag = "global.arcology_assembly_complete", name = "arcology" },
    { flag = "global.prime_rift_complete",        name = "prime_rift" },
}
local RESOURCE_ALIASES = { ironium = "steel", steel = "steel", carbonium = "carbonium", cobalt = "cobalt",
                           palladium = "palladium", titanium = "titanium", uranium = "uranium", energy = "energy" }

local function Log(msg) LogService:Log("[AP] " .. msg) end

class 'ap_rule' ( LuaGraphNode )

function ap_rule:__init()
    LuaGraphNode.__init(self, self)
end

function ap_rule:init()
    self.fsm = self:CreateStateMachine()
    self.fsm:AddState("tick", { execute = "OnTick" })
    self.fsm:ChangeState("tick")
    self:Start()
end

function ap_rule:OnLoad()
    self:Start()
end

function ap_rule:Start()
    g_ap_rule_owner = self
    self.reported = {}
    self.goals_reported = {}
    self.bound = false
    self.bound_reported = false
    self.mismatch_reported = false
    self.mode_warned = nil
    self.jungle_unlocked = false
    self.connected = nil
    self.mode = nil
    self.inbox = nil
    self.biome = nil
    self.survival_reported = -1
    self.survival_acc = 0
    self.status = "Archipelago: waiting for the client"
    self.messages = {}
    self.message_timer = 0
    self.status_timer = 0
    self.poll_timer = 0
    self.resync_timer = 0
    Log("HELLO " .. PROTOCOL)
    local ok, err = pcall(function() self:Poll(true) end)
    if not ok then Log("ERROR " .. tostring(err)) end
end

function ap_rule:OnTick(state, dt)
    if g_ap_rule_owner ~= self then return end   -- a newer instance is in charge
    self:TickHud(dt)
    self.survival_acc = self.survival_acc + dt
    self.poll_timer = self.poll_timer + dt
    self.resync_timer = self.resync_timer + dt
    if self.poll_timer < POLL_SECONDS then return end
    self.poll_timer = 0
    local full = self.resync_timer >= RESYNC_SECONDS
    if full then self.resync_timer = 0 end
    local ok, err = pcall(function() self:Poll(full) end)
    if not ok then Log("ERROR " .. tostring(err)) end
end

-- ---------------------------------------------------------------- HUD
function ap_rule:ShowStatus(text, seconds)
    self.status = text
    GuiService:ShowHudText(HUD_STATUS, text)
    self.status_timer = seconds or 8.0
end

function ap_rule:Notify(text)
    if #self.messages < 8 then self.messages[#self.messages + 1] = text end
end

function ap_rule:TickHud(dt)
    if self.status_timer > 0 then
        self.status_timer = self.status_timer - dt
        if self.status_timer <= 0 then GuiService:HideHudText(HUD_STATUS) end
    end
    if self.message_timer > 0 then
        self.message_timer = self.message_timer - dt
        if self.message_timer > 0 then return end
        GuiService:HideHudText(HUD_ITEM)
    end
    if #self.messages > 0 then
        GuiService:ShowHudText(HUD_ITEM, table.remove(self.messages, 1))
        self.message_timer = MESSAGE_SECONDS
    end
end

-- ---------------------------------------------------------------- mode
function ap_rule:DetectMode()
    local ctype = CampaignService:GetCurrentCampaignType()
    if ctype == "survival" then return "survival" end
    if ctype ~= "story" then return nil end
    if CampaignService:GetCampaignData():GetStringOrDefault("campaign_mode_open", "") == "true" then return "open" end
    return "story"
end

function ap_rule:ModeData()
    return AP_DATA.modes[self.mode]
end

-- ---------------------------------------------------------------- poll
function ap_rule:Poll(full)
    local mode = self:DetectMode()
    if mode == nil then return end
    if mode ~= self.mode then
        self.mode = mode
        Log("MODE " .. mode)
    end
    if mode == "open" and not self.jungle_unlocked then
        self.jungle_unlocked = true
        CampaignService:UnlockBiome("jungle")   -- the starting biome; the vanilla chain that unlocked it is cut
    end
    if mode == "survival" then
        local data = CampaignService:GetCampaignData()
        data:SetFloat(KEY_SURVIVAL, data:GetFloatOrDefault(KEY_SURVIVAL, 0) + self.survival_acc)
    end
    self.survival_acc = 0
    self:ApplyInbox(full)   -- first, so BOUND precedes the reports it vouches for
    if not self.bound then return end
    self:ReportDone(full)
    if mode == "open" then self:ReportBiome(full) end
    if mode == "survival" then self:ReportSurvival(full) end
    self:ReportGoals(full)
end

function ap_rule:IsDone(data, id)
    return data:GetIntOrDefault(KEY_DONE .. id, 0) == 1
end

function ap_rule:ReportDone(full)
    local data = CampaignService:GetCampaignData()
    local md = self:ModeData()
    local player = PlayerService:GetLeadingPlayer()
    -- builds and story missions are remembered once done (buildings can be upgraded or destroyed later)
    for _, b in ipairs(md.builds) do
        if not self:IsDone(data, b.id) then
            for _, bp in ipairs(b.blueprints) do
                local found = FindService:FindEntitiesByBlueprint(bp)
                if found and #found > 0 then
                    data:SetInt(KEY_DONE .. b.id, 1)
                    break
                end
            end
        end
    end
    if self.mode == "story" then
        for _, m in ipairs(AP_DATA.missions) do
            if not self:IsDone(data, m.id) and CampaignService:GetMissionStatus(m.mission) == MISSION_STATUS_WIN then
                data:SetInt(KEY_DONE .. m.id, 1)
            end
        end
    end
    local new, all = {}, {}
    local function add(id)
        all[#all + 1] = id
        if not self.reported[id] then
            self.reported[id] = true
            new[#new + 1] = id
        end
    end
    for name, id in pairs(md.locations) do
        if PlayerService:IsResearchUnlocked(player, name) then add(id) end
    end
    for _, b in ipairs(md.builds) do
        if self:IsDone(data, b.id) then add(b.id) end
    end
    if self.mode == "story" then
        for _, m in ipairs(AP_DATA.missions) do
            if self:IsDone(data, m.id) then add(m.id) end
        end
    end
    if full then
        Log("CHECKS " .. table.concat(all, ","))
    elseif #new > 0 then
        Log("CHECK " .. table.concat(new, ","))
    end
end

function ap_rule:ReportBiome(full)
    local biome = MissionService:GetCurrentBiomeName()
    if biome ~= self.biome or full then
        self.biome = biome
        Log("BIOME " .. tostring(biome))
    end
end

function ap_rule:ReportSurvival(full)
    local seconds = math.floor(CampaignService:GetCampaignData():GetFloatOrDefault(KEY_SURVIVAL, 0))
    if full or seconds - self.survival_reported >= 10 then
        self.survival_reported = seconds
        Log("SURVIVE " .. seconds)
    end
    local duration = DifficultyService:GetMissionDuration()
    if duration and duration > 0 and seconds >= duration and (full or not self.goals_reported.survival) then
        self.goals_reported.survival = true
        Log("GOAL survival")
    end
end

function ap_rule:ReportGoals(full)
    if self.mode == "survival" then return end
    local data = CampaignService:GetCampaignData()
    for _, g in ipairs(GOALS) do
        if data:GetStringOrDefault(g.flag, "") == "true" and (full or not self.goals_reported[g.name]) then
            self.goals_reported[g.name] = true
            Log("GOAL " .. g.name)
        end
    end
end

-- ---------------------------------------------------------------- items
local function GrantAwards(awards)
    -- every player in the session gets the reward (co-op shares one slot)
    local players = PlayerService:GetAllPlayers()
    for _, award in ipairs(awards) do
        for i = 1, #players do
            PlayerService:AddGlobalAward(award[1], award[2], players[i])
        end
    end
end

function ap_rule:ApplyItem(index, id, copy)
    local md = self:ModeData()
    if md.awards[id] then
        GrantAwards(md.awards[id])
    elseif md.progressive[id] then
        local level = md.progressive[id][copy]
        if level then GrantAwards(level) end
    elseif AP_DATA.biomes[id] then
        CampaignService:UnlockBiome(AP_DATA.biomes[id])
    elseif AP_DATA.fillers[id] then
        local f = AP_DATA.fillers[id]
        PlayerService:AddResourceAmount(PlayerService:GetLeadingPlayer(), f[1], f[2], false)
    else
        Log("UNKNOWN_ITEM " .. index .. " " .. tostring(id))
        return
    end
    Log("RECEIVED " .. index .. " " .. id)
end

function ap_rule:ApplyInbox(full)
    local chunk = loadfile(INBOX_PATH)
    if not chunk then return end
    local ok, inbox = pcall(chunk)
    if not ok or type(inbox) ~= "table" or type(inbox.items) ~= "table" then return end
    self.inbox = inbox

    local data = CampaignService:GetCampaignData()
    local session = tostring(inbox.session or "")
    if session == "" then return end
    if inbox.mode and inbox.mode ~= self.mode then
        self.bound = false
        if self.mode_warned ~= self.mode then
            self.mode_warned = self.mode
            self:ShowStatus("Archipelago: this slot is for the " .. tostring(inbox.mode) .. " mode, but this game is " ..
                            tostring(self.mode) .. ". Start a " .. tostring(inbox.mode) .. " game.", 20.0)
        end
        return
    end
    local bound = data:GetStringOrDefault(KEY_SESSION, "")
    if bound == "" then
        data:SetString(KEY_SESSION, session)   -- first connection for this campaign: bind it to this slot/seed
        data:SetInt(KEY_APPLIED, 0)
        bound = session
    end
    if bound ~= session then
        self.bound = false
        if not self.mismatch_reported then
            self.mismatch_reported = true
            Log("MISMATCH " .. bound)
            self:ShowStatus("Archipelago: this campaign belongs to another slot or seed. Start a new game.", 20.0)
        end
        return
    end
    self.bound = true
    if not self.bound_reported or full then
        self.bound_reported = true
        Log("BOUND " .. session)
    end
    if self.mode == "survival" and inbox.survival_map and not self.map_warned then
        local biome = MissionService:GetCurrentBiomeName()
        if biome and biome ~= "" and biome ~= inbox.survival_map then
            self.map_warned = true
            self:ShowStatus("Archipelago: this slot expects the " .. inbox.survival_map .. " survival map (this is " ..
                            biome .. "). Logic assumes " .. inbox.survival_map .. ".", 15.0)
        end
    end

    local connected = inbox.connected == true
    if connected ~= self.connected then
        self.connected = connected
        if connected then
            self:ShowStatus("Archipelago: connected as " .. tostring(inbox.player or "?") ..
                            " (" .. #inbox.items .. " items received)", 8.0)
        else
            self:ShowStatus("Archipelago: client disconnected", 8.0)
        end
    end

    local applied = data:GetIntOrDefault(KEY_APPLIED, 0)
    local total = #inbox.items
    if total > applied then
        local copies = {}
        local labels = type(inbox.labels) == "table" and inbox.labels or {}
        for i = 1, total do
            local id = inbox.items[i]
            copies[id] = (copies[id] or 0) + 1
            if i > applied then
                self:ApplyItem(i, id, copies[id])
                data:SetInt(KEY_APPLIED, i)
                if labels[i] then self:Notify("Archipelago: received " .. labels[i]) end
            end
        end
    end

    -- Energy Link withdrawals the client approved
    if type(inbox.grants) == "table" then
        local last = data:GetIntOrDefault(KEY_EL_GRANT, 0)
        for _, g in ipairs(inbox.grants) do
            if type(g) == "table" and g[1] and g[1] > last then
                if g[3] and g[3] > 0 then
                    PlayerService:AddResourceAmount(PlayerService:GetLeadingPlayer(), g[2], g[3], false)
                    self:Notify("Archipelago: withdrew " .. math.floor(g[3]) .. " " .. g[2] .. " from Energy Link")
                else
                    self:Notify("Archipelago: Energy Link had nothing to give for request " .. g[1])
                end
                last = g[1]
                data:SetInt(KEY_EL_GRANT, last)
            end
        end
    end
end

-- ---------------------------------------------------------------- console commands (called from the autoexec)
function ap_rule:StatusText()
    return self.status
end

function ap_rule:ShowTracker()
    local text = self.inbox and self.inbox.tracker
    if not text or text == "" then text = "Archipelago: no tracker data yet (is the client connected?)" end
    self:ShowStatus(text, 15.0)
end

function ap_rule:EnergyLinkReady()
    local inbox = self.inbox
    if not self.bound or not inbox then return false, "not linked to the client" end
    if inbox.energy_link ~= true then return false, "Energy Link is off for this slot" end
    if inbox.connected ~= true then return false, "the client is not connected" end
    return true
end

function ap_rule:EnergyLinkRequest(kind, args)
    local ready, why = self:EnergyLinkReady()
    if not ready then
        self:ShowStatus("Archipelago: Energy Link unavailable (" .. why .. ")", 8.0)
        return
    end
    local resource = RESOURCE_ALIASES[string.lower(tostring(args[1] or ""))]
    local amount = math.floor(tonumber(args[2] or "") or 0)
    if not resource or amount <= 0 then
        self:ShowStatus("Usage: ap_" .. kind .. " <carbonium|ironium|cobalt|palladium|titanium|uranium|energy> <amount>", 10.0)
        return
    end
    local player = PlayerService:GetLeadingPlayer()
    local data = CampaignService:GetCampaignData()
    if kind == "deposit" then
        local have = PlayerService:GetResourceAmount(player, resource)
        if have < amount then
            self:ShowStatus("Archipelago: you only have " .. math.floor(have) .. " " .. resource, 8.0)
            return
        end
        PlayerService:AddResourceAmount(player, resource, -amount, false)
    end
    local seq = data:GetIntOrDefault(KEY_EL_SEQ, 0) + 1
    data:SetInt(KEY_EL_SEQ, seq)
    Log((kind == "deposit" and "EL_DEPOSIT " or "EL_WITHDRAW ") .. seq .. " " .. resource .. " " .. amount)
    self:ShowStatus("Archipelago: " .. (kind == "deposit" and "deposited " or "requested ") .. amount .. " " ..
                    resource .. (kind == "deposit" and " into" or " from") .. " Energy Link", 6.0)
end

function ap_rule:EnergyLinkStatus()
    local inbox = self.inbox
    if not inbox or inbox.energy == nil then
        self:ShowStatus("Archipelago: Energy Link pool unknown (is the client connected?)", 8.0)
        return
    end
    self:ShowStatus("Archipelago: Energy Link pool " .. tostring(inbox.energy), 10.0)
end

return ap_rule
