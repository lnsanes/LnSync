package com.lnsanes.lnsync;

import net.minecraftforge.fml.common.Mod;

@Mod("lnsync")
public final class LnSyncMod {
    public LnSyncMod() {
        LaunchHook.clientGate();
    }
}
