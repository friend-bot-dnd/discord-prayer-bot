# The 91st Psalm audio: removing the Audible intro and outro (issue #69)

The recording shipped with the bot was an Audible download that still had the
Audible wrapper: "This is Audible" at the start and "Audible hopes you have
enjoyed this program" at the end. The file was replaced in place, same name,
same 160 kbit/s stereo 44.1 kHz MP3, same ID3 tags (title, artist, album
artist), so no code change was needed.

## How the cut points were found

No transcript was available offline, so the file was measured instead.

1. Decode to mono 16 kHz PCM and compute RMS in 20 ms windows:

   ```
   ffmpeg -i "The 91st Psalm.mp3" -ac 1 -ar 16000 -f s16le full.raw
   ```

   Runs of 120 ms or more above 3% of the peak were treated as sound.

2. That gave the structure of the file:

   | time (s) | what it is |
   | --- | --- |
   | 0.48 - 1.64 | "This is Audible" (three word-length bursts) |
   | 5.10 - 5.66 | Audible logo sound |
   | 6.44 - 7.00 | four short tones near 7.7 kHz (Audible marker) |
   | 7.14 - 127.96 | the psalm, continuous narration |
   | 128.0 - 144.5 | noise floor only (-78 dBFS) |
   | 144.50 - 146.62 | "Audible hopes you have enjoyed this program" |
   | 146.7 - 147.8 | digital silence |

3. The boundaries were checked against a spectrogram (`showspectrumpic`,
   log scale, 0-8 kHz) to confirm the psalm starts at 7.14 s and the last
   psalm word ends at 127.96 s. The psalm never has a gap longer than 2.7 s,
   so the 16.5 s silent stretch before the outro is unambiguous.

## The cut

```bash
ffmpeg -ss 7.05 -i "The 91st Psalm.mp3" -t 121.25 \
  -af "afade=t=in:st=0:d=0.05,afade=t=out:st=120.85:d=0.40" \
  -c:a libmp3lame -b:a 160k -ar 44100 -ac 2 \
  -map 0:a -map_metadata 0 -id3v2_version 3 -write_id3v1 1 out.mp3
```

Start 7.05 s keeps 0.09 s of silence before the first psalm word; end 128.30 s
keeps 0.34 s after the last word. Short fades stop clicks at both ends.

Result: 2:27.80 -> 2:01.25, 26.55 s removed.

## Check after the cut

The same RMS run detection on the new file shows the first sound at 0.08 s and
the last at 120.78 s, with no speech outside that range, so the intro and outro
are gone and no psalm words were lost.

The one-off script used for the measurement is not part of this repo; it is a
general "trim an Audible wrapper" tool and belongs in its own repo.
