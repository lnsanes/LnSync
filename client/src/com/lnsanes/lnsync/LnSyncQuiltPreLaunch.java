package com.lnsanes.lnsync;

import org.quiltmc.loader.api.ModContainer;
import org.quiltmc.loader.api.entrypoint.PreLaunchEntrypoint;

/** Quilt early hook: pull files before the game finishes launching. */
public final class LnSyncQuiltPreLaunch implements PreLaunchEntrypoint {
    @Override
    public void onPreLaunch(ModContainer mod) {
        LaunchHook.markEarly();
        LaunchHook.clientGate();
    }
}
