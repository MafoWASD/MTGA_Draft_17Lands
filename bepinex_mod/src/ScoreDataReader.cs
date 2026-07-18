using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json.Linq;

namespace ArenaPackOverlayMod
{
    public struct CardScore
    {
        public int Value;
        public double Gihwr;
    }

    // Reads the VALUE/GIHWR scores Python computes (via the existing
    // DraftAdvisor / 17Lands dataset pipeline - never reimplemented here,
    // see the project plan's "mod stays minimal" rationale) from a JSON
    // file Python writes to the OS temp directory, keyed by grpId. Read
    // fresh on every pack layout rather than cached/watched - a plain file
    // read is cheap enough at that cadence and avoids a second polling
    // thread inside the mod.
    public static class ScoreDataReader
    {
        private static readonly string DataFile = Path.Combine(Path.GetTempPath(), "ArenaPackOverlayMod", "scores.json");

        public static Dictionary<uint, CardScore> Read()
        {
            var result = new Dictionary<uint, CardScore>();
            string text;
            try
            {
                text = File.ReadAllText(DataFile);
            }
            catch (Exception)
            {
                return result; // no scores written yet - not an error
            }

            try
            {
                JObject obj = JObject.Parse(text);
                foreach (var prop in obj.Properties())
                {
                    if (!uint.TryParse(prop.Name, out uint grpId))
                    {
                        continue;
                    }
                    result[grpId] = new CardScore
                    {
                        Value = prop.Value.Value<int?>("value") ?? 0,
                        Gihwr = prop.Value.Value<double?>("gihwr") ?? 0,
                    };
                }
            }
            catch (Exception e)
            {
                // Most likely a torn read racing Python's own write - not
                // logged as an error, just try again on the next pack layout.
                Plugin.Log.LogDebug("[ScoreDataReader] Parse failed (likely a torn read): " + e.Message);
            }

            return result;
        }
    }
}
