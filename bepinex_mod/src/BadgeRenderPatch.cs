using System.Collections.Generic;
using HarmonyLib;
using TMPro;
using UnityEngine;
using Wotc.Mtga.Wrapper.Draft;

namespace ArenaPackOverlayMod
{
    // Renders the VALUE score badge on each pack card. Meta_CDC's built-in
    // "collection info" slot (_collectionAnchor/_collectionText) is
    // correctly positioned/styled, but reusing the LIVE object in place
    // didn't work - Arena's own Alt-key "hold to reveal extra info" logic
    // also controls that exact GameObject's active state every frame and
    // fights us for control. Cloning it instead gives an independent
    // GameObject nothing else in Arena is watching, while still inheriting
    // the correct font/material/Canvas setup for free.
    [HarmonyPatch(typeof(DraftPackHolder), "LayoutCards")]
    public static class BadgeRenderPatch
    {
        private const string BadgeName = "ValueBadge";

        private static readonly AccessTools.FieldRef<Meta_CDC, GameObject> CollectionAnchorRef =
            AccessTools.FieldRefAccess<Meta_CDC, GameObject>("_collectionAnchor");

        private static void Postfix(List<DraftPackCardView> ____allCardViews)
        {
            Dictionary<uint, CardScore> scores = ScoreDataReader.Read();

            for (int i = 0; i < ____allCardViews.Count; i++)
            {
                DraftPackCardView cardView = ____allCardViews[i];
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
                }
                else
                {
                    // No score for this card yet (Python hasn't caught up
                    // with this pack, or the mod just started) - hide
                    // rather than show a stale/placeholder number.
                    badge.SetActive(false);
                }
            }
        }
    }
}
