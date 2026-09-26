package com.lnsanes.lnsync;

import net.fabricmc.loader.api.entrypoint.PreLaunchEntrypoint;

/** Fabric early hook: pull files before the game finishes launching. */
public final class LnSyncFabricPreLaunch implements PreLaunchEntrypoint {
    @Override
    public void onPreLaunch() {
        LaunchHook.markEarly();
        LaunchHook.clientGate();
    }
}
