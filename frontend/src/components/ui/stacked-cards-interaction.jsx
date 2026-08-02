import { motion } from "framer-motion";
import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Satu kartu bertumpuk. Warna memakai token tema repo (bukan bg-white keras)
 * supaya ikut mode gelap seperti komponen lain di aplikasi ini.
 */
const Card = ({ className, image, children }) => (
  <div
    className={cn(
      "w-[350px] cursor-pointer h-[400px] overflow-hidden bg-card rounded-2xl shadow-[0_0_10px_rgba(0,0,0,0.02)] border border-border",
      className,
    )}
  >
    {image && (
      <div className="relative h-72 rounded-xl shadow-lg overflow-hidden w-[calc(100%-1rem)] mx-2 mt-2">
        <img src={image} alt="" className="object-cover mt-0 w-full h-full" />
      </div>
    )}
    {children && <div className="px-4 p-2 flex flex-col gap-y-2">{children}</div>}
  </div>
);

/**
 * Tumpukan kartu yang MENYEBAR saat disentuh/di-hover: kartu depan diam, kartu
 * kedua bergeser+miring ke kiri, kartu ketiga ke kanan.
 *
 * `spread` diekspor terpisah (lihat `hitungSebaran`) agar pemakai lain — mis.
 * kartu informasi aset di penampil foto — bisa memakai MODEL geraknya sambil
 * mengemudikannya dengan geseran jari, bukan hover.
 *
 * @param {Object} props
 * @param {{image?: string, title?: string, description?: string}[]} props.cards
 * @param {number} [props.spreadDistance] Jarak sebar mendatar (px).
 * @param {number} [props.rotationAngle] Sudut miring kartu belakang (derajat).
 * @param {number} [props.animationDelay] Jeda antar kartu (detik).
 */
const StackedCardsInteraction = ({
  cards,
  spreadDistance = 40,
  rotationAngle = 5,
  animationDelay = 0.1,
}) => {
  const [isHovering, setIsHovering] = useState(false);
  const limitedCards = (cards || []).slice(0, 3); // maksimal 3 kartu

  return (
    <div className="relative w-full h-full flex items-center justify-center">
      <div className="relative w-[350px] h-[400px]">
        {limitedCards.map((card, index) => {
          const isFirst = index === 0;
          const { x, rotate } = hitungSebaran(index, {
            spreadDistance,
            rotationAngle,
            aktif: isHovering,
          });

          return (
            <motion.div
              key={index}
              className={cn("absolute", isFirst ? "z-10" : "z-0")}
              initial={{ x: 0, rotate: 0 }}
              animate={{ x, rotate, zIndex: isFirst ? 10 : 0 }}
              transition={{
                duration: 0.3,
                ease: "easeInOut",
                delay: index * animationDelay,
                type: "spring",
              }}
              {...(isFirst && {
                onHoverStart: () => setIsHovering(true),
                onHoverEnd: () => setIsHovering(false),
              })}
            >
              <Card className={isFirst ? "z-10 cursor-pointer" : "z-0"} image={card.image}>
                {card.title && <h2 className="text-foreground font-semibold">{card.title}</h2>}
                {card.description && (
                  <p className="text-muted-foreground text-sm">{card.description}</p>
                )}
              </Card>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};

/**
 * Geser & miring satu kartu pada tumpukan. MURNI — dipakai komponen ini dan
 * penampil foto aset (kartu tetangga menyembul saat kartu depan digeser).
 *
 * index 0 = kartu depan (diam), 1 = menyebar ke kiri, 2 = ke kanan.
 * `intensitas` 0..1 memungkinkan sebaran mengikuti seberapa jauh jari menggeser
 * alih-alih hidup/mati begitu saja.
 */
function hitungSebaran(index, { spreadDistance = 40, rotationAngle = 5, aktif = false, intensitas = 1 } = {}) {
  if (!aktif || index === 0) return { x: 0, rotate: 0 };
  const k = Math.max(0, Math.min(1, intensitas));
  if (index === 1) return { x: -spreadDistance * k, rotate: -rotationAngle * k };
  return { x: spreadDistance * k, rotate: rotationAngle * k };
}

export { StackedCardsInteraction, Card, hitungSebaran };
