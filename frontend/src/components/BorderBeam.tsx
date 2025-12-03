interface BorderBeamProps {
  className?: string;
  duration?: number;
  borderWidth?: number;
  colorFrom?: string;
  colorTo?: string;
  delay?: number;
}

export const BorderBeam = ({
  className = "",
  duration = 8,
  borderWidth = 3,
  colorFrom = "#16a34a",
  colorTo = "#00d4ff",
  delay = 0,
}: BorderBeamProps) => {
  return (
    <>
      {/* Rotating gradient background */}
      <div
        className={`pointer-events-none absolute rounded-[inherit] overflow-hidden ${className}`}
        style={{
          inset: `-${borderWidth}px`,
          zIndex: 0,
        }}
      >
        <div
          className="absolute animate-spin"
          style={{
            width: '200%',
            height: '200%',
            top: '-50%',
            left: '-50%',
            animationDuration: `${duration}s`,
            animationDelay: `${delay}s`,
            background: `conic-gradient(
              from 0deg,
              transparent 0deg,
              ${colorFrom} 90deg,
              ${colorTo} 180deg,
              transparent 270deg
            )`,
          }}
        />
      </div>
    </>
  );
};
