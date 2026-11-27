-- Archipelago runtime game rule (open campaign).
--   Game -> client: log lines "[AP] <KIND> <args>" in Documents/The Riftbreaker/exor_logs.txt
--     HELLO <protocol>            rule started (new map or save loaded); a full snapshot follows
--     BOUND <session>             this campaign belongs to <session> (reports after it can be trusted)
--     MISMATCH <session>          this campaign belongs to another slot/seed; nothing is applied
--     CHECKS id,id,...            every completed research location (snapshot)
--     CHECK id,id                 newly completed research locations
--     GOAL arcology|prime_rift    campaign endgame milestones reached
--     RECEIVED <index> <item id>  an item was applied
--   Client -> game: <game>/archipelago/inbox.lua (polled with loadfile)
--     return { session = "<seed>:<slot>", connected = true, player = "<slot name>",
--              items = { <item id>, ... }, labels = { "<item> (from <player>)", ... } }
-- The number of applied items is stored in campaign data, so filler is granted exactly once.

require("lua/archipelago/ap_data.lua")

local PROTOCOL       = 2
local RESEARCH_PREFIX = "gui/menu/research/name/"
local INBOX_PATH     = "../archipelago/inbox.lua"   -- relative to bin/, the game's working directory
local POLL_SECONDS   = 2.0
local RESYNC_SECONDS = 30.0
local MESSAGE_SECONDS = 5.0
local KEY_APPLIED    = "archipelago.items_applied"
local KEY_SESSION    = "archipelago.session"
local HUD_STATUS     = "archipelago_status"
local HUD_ITEM       = "archipelago_item"

local GOALS = {
    { flag = "global.arcology_assembly_complete", name = "arcology" },
    { flag = "global.prime_rift_complete",        name = "prime_rift" },
}

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
    self.bound_reported = false
    self.mismatch_reported = false
    self.jungle_unlocked = false
    self.connected = nil
    self.status = "Archipelago: waiting for the client"
    self.messages = {}
    self.message_timer = 0
    self.status_timer = 0
    self.poll_timer = 0
    self.resync_timer = 0
    Log("HELLO " .. PROTOCOL)
    local ok, err = pcall(function()
        local list = PlayerService:GetUnlockedResearchesList()
        Log("DIAG unlocked_list=" .. tostring(list and #list))
        self:Poll(true)
    end)
    if not ok then Log("ERROR " .. tostring(err)) end
end

function ap_rule:OnTick(state, dt)
    if g_ap_rule_owner ~= self then return end   -- a newer instance is in charge
    self:TickHud(dt)
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

-- ---------------------------------------------------------------- poll
function ap_rule:Poll(full)
    -- Open campaign only (its main graph sets this flag at campaign start); the story campaign is untouched.
    if CampaignService:GetCampaignData():GetStringOrDefault("campaign_mode_open", "") ~= "true" then return end
    if not self.jungle_unlocked then
        self.jungle_unlocked = true
        CampaignService:UnlockBiome("jungle")   -- the starting biome; the vanilla chain that unlocked it is cut
    end
    self:ApplyInbox(full)   -- first, so BOUND precedes the reports it vouches for
    self:ReportResearch(full)
    self:ReportGoals(full)
end

function ap_rule:ReportResearch(full)
    local player = PlayerService:GetLeadingPlayer()
    local new, all = {}, {}
    for name, id in pairs(AP_DATA.locations) do
        if PlayerService:IsResearchUnlocked(player, RESEARCH_PREFIX .. name) then
            all[#all + 1] = id
            if not self.reported[id] then
                self.reported[id] = true
                new[#new + 1] = id
            end
        end
    end
    if full then
        Log("CHECKS " .. table.concat(all, ","))
    elseif #new > 0 then
        Log("CHECK " .. table.concat(new, ","))
    end
end

function ap_rule:ReportGoals(full)
    local data = CampaignService:GetCampaignData()
    for _, g in ipairs(GOALS) do
        if data:GetStringOrDefault(g.flag, "") == "true" and (full or not self.goals_reported[g.name]) then
            self.goals_reported[g.name] = true
            Log("GOAL " .. g.name)
        end
    end
end

-- ---------------------------------------------------------------- items
local function GrantAwards(player, awards)
    for _, award in ipairs(awards) do
        if not PlayerService:HasGlobalAward(award[1]) then
            PlayerService:AddGlobalAward(award[1], award[2], player)
        end
    end
end

function ap_rule:ApplyItem(player, index, id, copy)
    if AP_DATA.awards[id] then
        GrantAwards(player, AP_DATA.awards[id])
    elseif AP_DATA.progressive[id] then
        local level = AP_DATA.progressive[id][copy]
        if level then GrantAwards(player, level) end
    elseif AP_DATA.biomes[id] then
        CampaignService:UnlockBiome(AP_DATA.biomes[id])
    elseif AP_DATA.fillers[id] then
        local f = AP_DATA.fillers[id]
        PlayerService:AddResourceAmount(player, f[1], f[2], false)
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

    local data = CampaignService:GetCampaignData()
    local session = tostring(inbox.session or "")
    if session == "" then return end
    local bound = data:GetStringOrDefault(KEY_SESSION, "")
    if bound == "" then
        -- First connection for this campaign: bind it to this slot/seed.
        data:SetString(KEY_SESSION, session)
        data:SetInt(KEY_APPLIED, 0)
        bound = session
    end
    if bound ~= session then
        if not self.mismatch_reported then
            self.mismatch_reported = true
            Log("MISMATCH " .. bound)
            self:ShowStatus("Archipelago: this campaign belongs to another slot or seed. Start a new open campaign.", 20.0)
        end
        return
    end
    if not self.bound_reported or full then
        self.bound_reported = true
        Log("BOUND " .. session)
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
    if total <= applied then return end
    local player = PlayerService:GetLeadingPlayer()
    local copies = {}
    local labels = type(inbox.labels) == "table" and inbox.labels or {}
    for i = 1, total do
        local id = inbox.items[i]
        copies[id] = (copies[id] or 0) + 1
        if i > applied then
            self:ApplyItem(player, i, id, copies[id])
            data:SetInt(KEY_APPLIED, i)
            if labels[i] and #self.messages < 8 then
                self.messages[#self.messages + 1] = "Archipelago: received " .. labels[i]
            end
        end
    end
end

function ap_rule:StatusText()
    return self.status
end

return ap_rule
