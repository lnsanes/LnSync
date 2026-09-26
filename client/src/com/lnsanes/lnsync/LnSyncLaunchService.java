package com.lnsanes.lnsync;

import cpw.mods.modlauncher.api.IEnvironment;
import cpw.mods.modlauncher.api.ITransformationService;
import cpw.mods.modlauncher.api.ITransformer;
import cpw.mods.modlauncher.api.IncompatibleEnvironmentException;

import java.util.List;
import java.util.Set;

/** Runs file sync before Forge finishes scanning mods. */
public final class LnSyncLaunchService implements ITransformationService {
    @Override
    public String name() {
        return "lnsync";
    }

    @Override
    public void initialize(IEnvironment environment) {
        LaunchHook.markEarly();
        LaunchHook.clientGate();
    }

    @Override
    public void beginScanning(IEnvironment environment) {
        // no transformers
    }

    @Override
    public void onLoad(IEnvironment env, Set<String> otherServices) throws IncompatibleEnvironmentException {
        // sync already done in initialize
    }

    @Override
    public List<ITransformer> transformers() {
        return List.of();
    }
}
