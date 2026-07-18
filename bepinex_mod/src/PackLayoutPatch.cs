using System.Collections.Generic;
using System.Text;
using HarmonyLib;
using Wotc.Mtga.Wrapper.Draft;

namespace ArenaPackOverlayMod
{
    // DraftPackHolder.LayoutCards assigns each card's on-screen grid position
    // purely from its index in the already-populated _allCardViews list (row =
    // index / columnCount, column = index % columnCount) - see Core.dll. That
    // list's order is Arena's own final, already-sorted display order, so
    // reading it here sidesteps the log's arbitrary pack order entirely.
    [HarmonyPatch(typeof(DraftPackHolder), "LayoutCards")]
    public static class PackLayoutPatch
    {
        // Harmony's private-field injection prepends "___" to the exact field
        // name - the field itself is "_allCardViews" (already has a leading
        // underscore), so the parameter name needs four underscores total.
        private static void Prefix(int columnCount, int rowCount, List<DraftPackCardView> ____allCardViews)
        {
            var slotGrpIds = new uint[____allCardViews.Count];
            var sb = new StringBuilder();
            sb.Append("[PackLayout] columnCount=").Append(columnCount)
              .Append(" rowCount=").Append(rowCount)
              .Append(" cards=").Append(____allCardViews.Count)
              .Append(" -> ");

            for (int i = 0; i < ____allCardViews.Count; i++)
            {
                // .Instance is null for draft-pack cards (they're not live GRE
                // game objects yet - drafting is client-side only). .Printing
                // is always populated regardless, and carries the same GrpId.
                uint grpId = 0;
                var currentCard = ____allCardViews[i].CurrentCard;
                if (currentCard != null && currentCard.Card != null && currentCard.Card.Printing != null)
                {
                    grpId = currentCard.Card.Printing.GrpId;
                }
                slotGrpIds[i] = grpId;
                sb.Append('[').Append(i).Append("]=").Append(grpId).Append(' ');
            }

            Plugin.Log.LogInfo(sb.ToString());
            PackDataWriter.WritePackLayout(slotGrpIds);
        }
    }
}
