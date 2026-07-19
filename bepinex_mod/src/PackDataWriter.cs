using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace ArenaPackOverlayMod
{
    // Writes the current pack's slot-index -> grpId mapping to a JSON file
    // in the OS temp directory, atomically (write to a .tmp file, then
    // replace) so Python never reads a half-written file mid-poll.
    //
    // A loopback TCP socket was tried first (see git history) and rejected:
    // the listener reported itself bound (Server.IsBound == true,
    // LocalEndpoint resolved correctly) but never showed up in the OS's own
    // connection table (verified via PowerShell Get-NetTCPConnection against
    // Arena's real PID - it had other genuine listening/established sockets,
    // just never ours), and no firewall rule fixed it. Root cause undetermined
    // - some sandboxing/security layer around Arena's process most likely.
    // A file has no such surface: same OS temp directory, same Windows user
    // account, both sides just do ordinary file I/O.
    public static class PackDataWriter
    {
        private static readonly string DataDir = Path.Combine(Path.GetTempPath(), "ArenaPackOverlayMod");
        private static readonly string DataFile = Path.Combine(DataDir, "pack_layout.json");
        private static readonly string TempFile = DataFile + ".tmp";

        public static void Init()
        {
            try
            {
                Directory.CreateDirectory(DataDir);
                Plugin.Log.LogInfo($"[PackDataWriter] Writing pack layout to {DataFile}.");
            }
            catch (Exception e)
            {
                Plugin.Log.LogError("[PackDataWriter] Failed to create data directory: " + e);
            }
        }

        // Serializes WriteWithRetry so overlapping background write tasks
        // (see below) never race each other on TempFile/DataFile.
        private static readonly object WriteLock = new object();

        // slotGrpIds[i] = grpId shown at slot index i (0 for an unresolved
        // slot - shouldn't happen given LayoutCards always has real cards,
        // but callers should treat 0 as "no card"). Builds the JSON on the
        // calling thread (cheap) but performs the actual file write on a
        // background thread - real capture showed Python's own 250ms poll
        // occasionally has pack_layout.json open for reading at the exact
        // moment this runs, and Windows won't let File.Delete/Move touch a
        // file that's currently open elsewhere. That's a transient, sub-
        // millisecond conflict worth a few retries, but retrying with
        // Thread.Sleep must never happen on Unity's main thread (this
        // method is called synchronously from a Harmony patch on
        // DraftPackHolder.LayoutCards, which itself fires several times in
        // quick succession per pack reveal - each call spawns its own
        // background write task, so WriteLock also stops those from
        // racing each other, which is what actually caused the write
        // failures seen in real capture, not just contention with Python).
        public static void WritePackLayout(uint[] slotGrpIds)
        {
            string json = BuildJson(slotGrpIds);
            Task.Run(() =>
            {
                lock (WriteLock)
                {
                    WriteWithRetry(json);
                }
            });
        }

        private static string BuildJson(uint[] slotGrpIds)
        {
            var sb = new StringBuilder();
            sb.Append("{\"schema_version\":1,\"timestamp\":")
              .Append(DateTimeOffset.UtcNow.ToUnixTimeMilliseconds())
              .Append(",\"slots\":[");
            for (int i = 0; i < slotGrpIds.Length; i++)
            {
                if (i > 0)
                {
                    sb.Append(',');
                }
                sb.Append("{\"index\":").Append(i).Append(",\"grp_id\":").Append(slotGrpIds[i]).Append('}');
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private const int MaxAttempts = 10;
        private const int RetryDelayMs = 20;

        private static void WriteWithRetry(string json)
        {
            for (int attempt = 1; attempt <= MaxAttempts; attempt++)
            {
                try
                {
                    File.WriteAllText(TempFile, json, Encoding.UTF8);
                    // File.Replace/Move an existing target isn't allowed on
                    // all platforms; delete-then-move is fine for our
                    // single-writer case (only this method ever writes
                    // DataFile).
                    if (File.Exists(DataFile))
                    {
                        File.Delete(DataFile);
                    }
                    File.Move(TempFile, DataFile);
                    return;
                }
                catch (IOException) when (attempt < MaxAttempts)
                {
                    Thread.Sleep(RetryDelayMs);
                }
                catch (Exception e)
                {
                    Plugin.Log.LogWarning("[PackDataWriter] Failed to write pack layout: " + e);
                    return;
                }
            }
            Plugin.Log.LogWarning(
                $"[PackDataWriter] Failed to write pack layout after {MaxAttempts} attempts (file kept locked by a reader)."
            );
        }
    }
}
