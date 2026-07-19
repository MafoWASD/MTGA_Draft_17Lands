using System.Collections.Generic;
using HarmonyLib;
using TMPro;
using UnityEngine;
using Wotc.Mtga.Wrapper.Draft;

namespace ArenaPackOverlayMod
{
    // Renders the VALUE score badge on each pack card by cloning Meta_CDC's
    // built-in "collection info" slot (_collectionAnchor/_collectionText) -
    // correctly positioned/styled for free, since it's a real clone of an
    // existing Arena UI element rather than something built from scratch.
    //
    // Reusing the LIVE object in place didn't work - Arena's own Alt-key
    // "hold to reveal extra info" logic also controls that exact
    // GameObject's active state every frame and fights us for control.
    // Cloning it instead gives an independent GameObject nothing else in
    // Arena is watching.
    //
    // Getting periodic (non-LayoutCards-triggered) updates to actually
    // render was the real fight here, not the badge element itself: our
    // own plugin's MonoBehaviour.Update() never fired at all (confirmed via
    // an unconditional log statement that never printed), for reasons never
    // pinned down. Fixed by piggybacking on DraftPackHolder's own Update()
    // instead (see ScoreRefreshTickPatch.cs) - once that was driving the
    // periodic re-application, this cloned-element approach rendered fine
    // on its own, same as the direct-postfix case always did.
    [HarmonyPatch(typeof(DraftPackHolder), "LayoutCards")]
    public static class BadgeRenderPatch
    {
        private const string BadgeName = "ValueBadge";

        private static readonly AccessTools.FieldRef<Meta_CDC, GameObject> CollectionAnchorRef =
            AccessTools.FieldRefAccess<Meta_CDC, GameObject>("_collectionAnchor");

        // The most recent pack's card views, so ScoreRefreshTickPatch can
        // re-apply scores periodically without needing another LayoutCards
        // event.
        internal static List<DraftPackCardView> LastCardViews;

        private static void Postfix(List<DraftPackCardView> ____allCardViews)
        {
            LastCardViews = ____allCardViews;
            ApplyScores(____allCardViews);
        }

        internal static void ApplyScores(List<DraftPackCardView> cardViews)
        {
            if (cardViews == null)
            {
                return;
            }

            Dictionary<uint, CardScore> scores = ScoreDataReader.Read();
            int matched = 0;

            for (int i = 0; i < cardViews.Count; i++)
            {
                DraftPackCardView cardView = cardViews[i];
                Meta_CDC cdc = cardView.CardView;
                if (cdc == null)
                {
                    continue;
                }

                GameObject template = CollectionAnchorRef(cdc);
                if (template == null)
                {
                    continue;
                }

                Transform parent = template.transform.parent;
                Transform existing = parent.Find(BadgeName);
                GameObject badge;
                if (existing != null)
                {
                    badge = existing.gameObject;
                }
                else
                {
                    badge = Object.Instantiate(template, parent);
                    badge.name = BadgeName;
                    // Offset tuned live in UnityExplorer against a real card
                    // (moved down near the power/toughness box, clear of the
                    // mana-cost icons the default collection-info slot sits
                    // under).
                    badge.transform.localPosition = template.transform.localPosition + new Vector3(-1.3f, -4.8836f, 0f);
                }

                Transform checkMark = badge.transform.Find("Collection_CheckMark");
                if (checkMark != null)
                {
                    checkMark.gameObject.SetActive(false);
                }

                TMP_Text text = badge.GetComponentInChildren<TMP_Text>(true);
                if (text == null)
                {
                    continue;
                }
                text.transform.parent.gameObject.SetActive(true);

                uint grpId = 0;
                var currentCard = cardView.CurrentCard;
                if (currentCard != null && currentCard.Card != null && currentCard.Card.Printing != null)
                {
                    grpId = currentCard.Card.Printing.GrpId;
                }

                if (grpId != 0 && scores.TryGetValue(grpId, out CardScore score))
                {
                    badge.SetActive(true);
                    text.SetText(score.Value.ToString());
                    matched++;
                }
                else
                {
                    // No score for this card yet (Python hasn't caught up
                    // with this pack, or the mod just started) - hide
                    // rather than show a stale/placeholder number. The
                    // periodic tick (ScoreRefreshTickPatch) will pick it up
                    // once Python writes scores.json for this pack.
                    badge.SetActive(false);
                }
            }

            Plugin.Log.LogInfo($"[BadgeRenderPatch] ApplyScores: matched {matched}/{cardViews.Count} cards against {scores.Count} scores in scores.json.");
        }
    }
}
