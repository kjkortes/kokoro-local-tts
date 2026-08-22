import {useCallback, useEffect, useState, type RefObject} from "react";


export function useAudioTransport(audioRef: RefObject<HTMLAudioElement | null>, fallbackDuration = 0) {
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(fallbackDuration);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const updateTime = () => setCurrentTime(audio.currentTime || 0);
    const updateDuration = () => setDuration(Number.isFinite(audio.duration) ? audio.duration : fallbackDuration);
    const stop = () => setPlaying(false);
    audio.addEventListener("timeupdate", updateTime);
    audio.addEventListener("durationchange", updateDuration);
    audio.addEventListener("ended", stop);
    audio.addEventListener("pause", stop);
    audio.addEventListener("play", () => setPlaying(true));
    return () => {
      audio.removeEventListener("timeupdate", updateTime);
      audio.removeEventListener("durationchange", updateDuration);
      audio.removeEventListener("ended", stop);
      audio.removeEventListener("pause", stop);
    };
  }, [audioRef, fallbackDuration]);

  const toggle = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      await audio.play();
      setPlaying(true);
    }
  }, [audioRef, playing]);

  const seek = useCallback((value: number) => {
    const audio = audioRef.current;
    if (audio) audio.currentTime = value;
    setCurrentTime(value);
  }, [audioRef]);

  return {playing, currentTime, duration, toggle, seek};
}

