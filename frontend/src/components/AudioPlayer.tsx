interface AudioPlayerProps {
  src: string;
}

export default function AudioPlayer({ src }: AudioPlayerProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 flex flex-col gap-2">
      <p className="text-sm text-gray-400 truncate">{src.split('/').pop()}</p>
      <audio
        controls
        className="w-full"
        src={src}
        preload="metadata"
      >
        Your browser does not support the audio element.
      </audio>
    </div>
  );
}
