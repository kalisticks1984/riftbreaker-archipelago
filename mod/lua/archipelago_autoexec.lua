-- Archipelago for The Riftbreaker (open campaign). Run automatically by the game (lua/*_autoexec.lua).
if ( not is_server ) then
    return
end

require("lua/archipelago/ap_data.lua")

-- Attach the polling rule once per loaded map. A rule restored from a save registers itself
-- (g_ap_rule_owner) in its OnLoad before players are initialized, so it is not added twice.
local function AP_Attach()
    -- The open campaign's type is "story"; the rule itself idles unless campaign_mode_open is set.
    if ( CampaignService:GetCurrentCampaignType() ~= "story" ) then return end
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

-- Console: open the research screen anywhere (no Communications Hub needed).
ConsoleService:RegisterCommand("ap_research", function(args)
    local player = PlayerService:GetLeadingPlayer()
    local mech = PlayerService:GetPlayerControlledEnt(player)
    QueueEvent("OpenResearchRequest", mech, player)
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

-- Console: show the Archipelago status on the HUD.
ConsoleService:RegisterCommand("ap_status", function(args)
    if ( g_ap_rule_owner ~= nil ) then
        g_ap_rule_owner:ShowStatus(g_ap_rule_owner:StatusText(), 8.0)
    else
        GuiService:ShowHudText("archipelago_status", "Archipelago: mod loaded, but not active in this campaign")
    end
end)
