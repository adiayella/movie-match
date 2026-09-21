import { useState } from "react";
import { motion, PanInfo } from "framer-motion";
import { TitleCard } from "../lib/api";

interface Props {
  cards: TitleCard[];
  onSwipe: (card: TitleCard, direction: "left" | "right") => void;
}

export default function SwipeDeck({ cards, onSwipe }: Props) {
  const [index, setIndex] = useState(0);

  if (index >= cards.length) {
    return (
      <div className="center-col">
        <div className="spinner" />
        <p>Waiting for your partner to finish swiping...</p>
      </div>
    );
  }

  const card = cards[index];
  const nextCard = cards[index + 1];

  function handleSwipe(direction: "left" | "right") {
    onSwipe(card, direction);
    setIndex((i) => i + 1);
  }

  function handleDragEnd(_e: unknown, info: PanInfo) {
    if (info.offset.x > 120) {
      handleSwipe("right");
    } else if (info.offset.x < -120) {
      handleSwipe("left");
    }
  }

  return (
    <div>
      <div className="swipe-deck">
        {nextCard && (
          <div className="swipe-card" style={{ transform: "scale(0.96)", zIndex: 1 }}>
            <CardContent card={nextCard} />
          </div>
        )}
        <motion.div
          key={card.tmdb_id}
          className="swipe-card"
          style={{ zIndex: 2 }}
          drag="x"
          dragConstraints={{ left: 0, right: 0 }}
          onDragEnd={handleDragEnd}
          whileDrag={{ rotate: 8 }}
        >
          <CardContent card={card} />
        </motion.div>
      </div>
      <div className="swipe-actions">
        <button className="btn-pass" onClick={() => handleSwipe("left")} aria-label="Pass">
          ✕
        </button>
        <button className="btn-like" onClick={() => handleSwipe("right")} aria-label="Like">
          ♥
        </button>
      </div>
    </div>
  );
}

function CardContent({ card }: { card: TitleCard }) {
  return (
    <>
      {card.poster_url ? (
        <img src={card.poster_url} alt={card.title} draggable={false} />
      ) : (
        <div style={{ height: "60%", background: "#eee" }} />
      )}
      <div className="info">
        <h3>
          {card.title} {card.year ? `(${card.year})` : ""}
        </h3>
        <p>
          {card.media_type === "tv" ? "Series" : "Movie"}
          {card.imdb_rating ? ` · ⭐ ${card.imdb_rating.toFixed(1)}` : ""}
          {card.runtime ? ` · ${card.runtime} min` : ""}
        </p>
        <p>{card.synopsis}</p>
      </div>
    </>
  );
}
