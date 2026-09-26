package com.lnsanes.lnsync;

import net.neoforged.fml.common.Mod;

@Mod("lnsync")
public final class LnSyncNeoForgeMod {
    public LnSyncNeoForgeMod() {
        LaunchHook.clientGate();
    }
}
