/**
 * One landing video plays at a time: the hero loop, a gallery hover preview or the
 * lightbox clip. Starting one pauses the previous, so a hovered grid never stacks
 * decoders on a laptop.
 */
let playing: HTMLVideoElement | null = null;

export function playExclusive(video: HTMLVideoElement): void {
  if (playing && playing !== video) pauseSafely(playing);
  playing = video;
  try {
    void video.play()?.catch(() => {});
  } catch {
    /* jsdom has no media stack; autoplay rejections are already swallowed above. */
  }
}

/** Pause, rewind and give up the slot. Safe to call on an element that never played. */
export function stopVideo(video: HTMLVideoElement): void {
  pauseSafely(video);
  try {
    video.currentTime = 0;
  } catch {
    /* jsdom throws on seeking an element with no media. */
  }
  releaseVideo(video);
}

export function releaseVideo(video: HTMLVideoElement): void {
  if (playing === video) playing = null;
}

/** Test seam: the registry is module state, so suites reset it between renders. */
export function resetVideoRegistry(): void {
  playing = null;
}

function pauseSafely(video: HTMLVideoElement): void {
  try {
    video.pause();
  } catch {
    /* jsdom has no media stack. */
  }
}
