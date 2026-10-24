#!/usr/bin/env bash
# Build a minimal, LGPL-only FFmpeg for PyAV (audio decoding for faster-whisper).
#
#   packaging/build_ffmpeg_lgpl.sh <install-prefix>
#
# Why: every PyAV wheel on PyPI bundles FFmpeg linked against libx264 and
# libx265, which are GPL. MDMT only *decodes audio*, so release builds use
# this FFmpeg instead: FFmpeg's own native code only (no --enable-gpl, no
# external codec libraries, --disable-autodetect so nothing from the build
# machine sneaks in), licensed LGPL-2.1-or-later. PyAV is then compiled from
# source against it (see .github/workflows/build.yml).
#
# Runs on Linux, macOS, and Windows (MSYS2 bash with the MSVC environment
# loaded; FFmpeg is built with --toolchain=msvc so PyAV can link to it).
set -euo pipefail

PREFIX=${1:?usage: build_ffmpeg_lgpl.sh <install-prefix>}
VERSION=8.1.2
SHA256=464beb5e7bf0c311e68b45ae2f04e9cc2af88851abb4082231742a74d97b524c
WORK=${FFMPEG_BUILD_DIR:-$(mktemp -d)}

mkdir -p "$PREFIX" "$WORK"
PREFIX=$(cd "$PREFIX" && pwd)
cd "$WORK"

if [ ! -f "ffmpeg-$VERSION.tar.xz" ]; then
  curl -fsSL -o "ffmpeg-$VERSION.tar.xz" "https://ffmpeg.org/releases/ffmpeg-$VERSION.tar.xz"
fi
echo "$SHA256  ffmpeg-$VERSION.tar.xz" | sha256sum -c -
rm -rf "ffmpeg-$VERSION"
tar xf "ffmpeg-$VERSION.tar.xz"
cd "ffmpeg-$VERSION"

# Containers MDMT accepts (Audio_Transcription.AUDIO_FORMATS) and the audio
# codecs found in them.  Native FFmpeg implementations only.
DEMUXERS=mp3,aac,mov,ogg,matroska,wav,flac,mpegps,mpegts,aiff,ac3,eac3
# Raw video demuxers are never opened directly, but MPEG-PS uses their probe
# functions to recognise video streams (otherwise video is mislabelled audio).
DEMUXERS+=,mpegvideo,m4v,h264,hevc
DECODERS=mp3,mp3float,mp2,mp2float,mp1,mp1float,aac,aac_fixed,aac_latm,alac,opus,vorbis,flac,\
ac3,ac3_fixed,eac3,pcm_s16le,pcm_s16be,pcm_s24le,pcm_s24be,pcm_s32le,pcm_f32le,pcm_f64le,pcm_u8,\
pcm_alaw,pcm_mulaw,adpcm_ima_wav,adpcm_ms
# Video parsers let the demuxers identify (and skip) video streams in
# .mp4/.mpeg/.webm files; without them probing can mislabel video as audio.
PARSERS=aac,aac_latm,mpegaudio,opus,vorbis,flac,ac3,mpegvideo,mpeg4video,h264,hevc,vp8,vp9,av1
# A few native encoders/muxers, used by the test suite to produce every
# input format from one fixture.
ENCODERS=pcm_s16le,flac,aac,opus
MUXERS=wav,flac,ogg,webm,matroska,mp4,ipod
# PyAV's AudioResampler runs an audio filter graph.
FILTERS=abuffer,abuffersink,aresample,aformat,anull,buffer,buffersink,format,null

EXTRA=()
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) EXTRA+=(--toolchain=msvc --target-os=win64 --arch=x86_64) ;;
  Darwin) EXTRA+=(--extra-cflags=-mmacosx-version-min=15.0 --extra-ldflags=-mmacosx-version-min=15.0) ;;
esac

./configure \
  --prefix="$PREFIX" \
  --enable-shared --disable-static --enable-pic \
  --disable-autodetect --disable-programs --disable-doc --disable-debug \
  --disable-network --disable-x86asm \
  --disable-everything \
  --enable-protocol=file,pipe \
  --enable-demuxer="$DEMUXERS" \
  --enable-decoder="$DECODERS" \
  --enable-parser="$PARSERS" \
  --enable-encoder="$ENCODERS" \
  --enable-muxer="$MUXERS" \
  --enable-filter="$FILTERS" \
  --enable-swresample \
  "${EXTRA[@]}"

# Refuse to install anything that is not LGPL.
if grep -qE '^#define (CONFIG_GPL|CONFIG_NONFREE) 1' config.h; then
  echo "error: configure produced a GPL/nonfree build" >&2
  exit 1
fi

make -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
make install
cp COPYING.LGPLv2.1 "$PREFIX/"
echo "FFmpeg $VERSION (LGPL) installed to $PREFIX"
