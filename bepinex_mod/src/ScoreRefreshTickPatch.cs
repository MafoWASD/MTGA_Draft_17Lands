using HarmonyLib;
using UnityEngine;
using Wotc.Mtga.Wrapper.Draft;

namespace ArenaPackOverlayMod
{
    // Piggybacks on DraftPackHolder's OWN Update() (the one responsible for
    // the automatic aspect-ratio relayout we've observed happening on its
    // own) to periodically re-apply badge scores. Our own plugin's
    // MonoBehaviour.Update() never actually fired (confirmed: every
    // successful score match in the log directly follows a real
    // LayoutCards call, never on its own, even with an unconditional log
    // statement at the very top of Update() that never printed) - reason
    // undetermined, but DraftPackHolder.Update() is proven to run every
    // frame while a pack is on screen, so patch that instead of trusting
    // our own MonoBehaviour lifecycle.
    [HarmonyPatch(typeof(DraftPackHolder), "Update")]
    public static class ScoreRefreshTickPatch
    {
        private const float ScoreRefreshIntervalSec = 0.5f;
        private static float _nextScoreRefresh;

        private static void Postfix()
        {
            if (Time.unscaledTime < _nextScoreRefresh)
            {
                return;
            }
            _nextScoreRefresh = Time.unscaledTime + ScoreRefreshIntervalSec;

            try
            {
                BadgeRenderPatch.ApplyScores(BadgeRenderPatch.LastCardViews);
            }
            catch (System.Exception e)
            {
                Plugin.Log.LogWarning("[ScoreRefreshTickPatch] Periodic ApplyScores tick failed: " + e);
            }
        }
    }
}
