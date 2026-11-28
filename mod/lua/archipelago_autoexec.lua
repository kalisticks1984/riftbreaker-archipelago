-- Archipelago for The Riftbreaker (open campaign, story campaign, survival). Run automatically by the game
-- (lua/*_autoexec.lua). Only the host runs it: in co-op the host's game and client bridge one shared slot.
if ( not is_server ) then
    return
end

require("lua/archipelago/ap_data.lua")

-- Attach the polling rule once per loaded map. A rule restored from a save registers itself
-- (g_ap_rule_owner) in its OnLoad before players are initialized, so it is not added twice.
local function AP_Attach()
    local ctype = CampaignService:GetCurrentCampaignType()
    if ( ctype ~= "story" and ctype ~= "survival" ) then return end   -- the open campaign's type is "story"
    if ( g_ap_rule_owner ~= nil ) then return end
    local ok, err = pcall(function()
        MissionService:AddGameRule( "lua/archipelago/ap_rule.lua", "" )
    end)
    if ok then
        LogService:Log("[AP] ATTACH")
    else
        LogService:Log("[AP] ATTACH_ERROR " .. tostring(err))
    end
end

RegisterGlobalEventHandler("PlayerInitializedEvent", function(evt)
    AP_Attach()
end)

local function WithRule(fn)
    if ( g_ap_rule_owner ~= nil ) then
        fn(g_ap_rule_owner)
    else
        GuiService:ShowHudText("archipelago_status", "Archipelago: mod loaded, but not active in this game")
    end
end

-- Console: open the research screen anywhere.
ConsoleService:RegisterCommand("ap_research", function(args)
    local player = PlayerService:GetLeadingPlayer()
    QueueEvent("OpenResearchRequest", PlayerService:GetPlayerControlledEnt(player), player)
end)

-- Console (testing aid): place a finished Communications Hub next to the mech for free.
-- The research screen is enabled only while the player owns a building whose limit_name is
-- "communications_hub" (native IsResearchEnabled), so this is the supported way to unlock it.
ConsoleService:RegisterCommand("ap_hub", function(args)
    local player = PlayerService:GetLeadingPlayer()
    local mech = PlayerService:GetPlayerControlledEnt(player)
    local bp = "buildings/main/communications_hub"
    local pos = FindService:FindEmptySpotForBuildingRadius(mech, 25.0, bp, "", "", player)
    if ( pos.first == false ) then
        GuiService:ShowHudText("archipelago_status", "Archipelago: no free space for a Communications Hub nearby")
        return
    end
    PlayerService:BuildBuildingAtSpot(bp, pos.second, player)
    GuiService:ShowHudText("archipelago_status", "Archipelago: Communications Hub placed")
end)

ConsoleService:RegisterCommand("ap_status", function(args)
    WithRule(function(rule) rule:ShowStatus(rule:StatusText(), 8.0) end)
end)

-- Console: non-research checks (builds, missions, arrivals, survival time) and what is in logic.
ConsoleService:RegisterCommand("ap_tracker", function(args)
    WithRule(function(rule) rule:ShowTracker() end)
end)

-- Console: Energy Link. ap_deposit / ap_withdraw <resource|energy> <amount>, ap_energylink.
ConsoleService:RegisterCommand("ap_deposit", function(args)
    WithRule(function(rule) rule:EnergyLinkRequest("deposit", args) end)
end)
ConsoleService:RegisterCommand("ap_withdraw", function(args)
    WithRule(function(rule) rule:EnergyLinkRequest("withdraw", args) end)
end)
ConsoleService:RegisterCommand("ap_energylink", function(args)
    WithRule(function(rule) rule:EnergyLinkStatus() end)
end)
