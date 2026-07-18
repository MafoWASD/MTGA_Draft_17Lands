using BepInEx;
using BepInEx.Logging;
using HarmonyLib;

namespace ArenaPackOverlayMod
{
    [BepInPlugin(PluginGuid, PluginName, PluginVersion)]
    public class Plugin : BaseUnityPlugin
    {
        public const string PluginGuid = "com.mafowasd.arenapackoverlaymod";
        public const string PluginName = "Arena Pack Overlay Mod";
        public const string PluginVersion = "0.1.0";

        internal static ManualLogSource Log;

        private void Awake()
        {
            Log = Logger;
            Log.LogInfo($"{PluginName} v{PluginVersion} loaded.");

            var harmony = new Harmony(PluginGuid);
            harmony.PatchAll();

            PackDataWriter.Init();
        }
    }
}
