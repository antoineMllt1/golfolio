// Le plan des deux trous, vus du dessus. Repère du dessin : 120 × 280, le départ en bas, le green en
// haut. « spots » donne la place de la balle à chaque arrêt (numéro de l'arrêt → [x, y]) ; « pin » est
// le trou, où la balle finit. Les distances restent crédibles pour un joueur : sur le par 5 le bois 3
// va plus loin que le fer long, et le putt de 3 m est plus long que celui de 1,5 m.
export const VIEW = { w: 120, h: 280 };

export const COURSE = [
  {
    n: 1,
    // Par 5 en coude à droite : le départ, le fairway qui commence plus loin, le green tout en haut.
    rough:
      'M48 272C36 272 28 264 26 250C20 222 18 190 24 160C29 136 40 116 46 98C50 84 50 66 56 50C62 32 84 22 100 30C116 38 120 58 112 76C104 94 94 112 88 134C82 158 80 190 78 222C77 244 74 262 64 268C59 271 54 272 48 272Z',
    fairway:
      'M46 230C40 228 35 220 33 210C29 192 30 172 35 156C40 140 50 128 57 114C62 104 65 94 69 86C72 79 80 74 88 77C95 80 96 89 92 98C87 110 80 122 75 136C69 152 66 170 65 188C64 204 64 216 60 224C57 230 52 232 46 230Z',
    green: { cx: 87, cy: 50, rx: 18, ry: 13, rot: -24 },
    bunkers: [
      'M24 184C21 178 24 170 30 171C35 172 36 180 32 185C30 188 26 188 24 184Z',
      'M77 156C74 151 77 144 83 145C88 146 88 154 85 158C82 161 79 160 77 156Z',
      'M59 64C56 59 59 53 64 54C68 55 69 61 66 65C64 67 61 67 59 64Z',
      'M103 70C100 65 103 59 108 60C112 61 113 67 110 71C108 73 105 73 103 70Z',
    ],
    tee: { x: 41.5, y: 256, w: 13, h: 7, rot: -6 },
    pin: [91, 46],
    spots: { 0: [48, 259.5], 1: [51, 156], 2: [72, 68], 3: [83.5, 53.5] },
  },
  {
    n: 2,
    // Par 3 : le départ, l'eau à survoler, le green.
    rough:
      'M56 272C42 272 34 264 34 252C34 238 26 226 16 216C4 204 4 178 12 160C18 146 20 132 18 116C14 88 26 52 56 42C88 32 114 54 114 86C114 106 108 122 108 140C108 158 116 176 110 196C104 216 84 224 80 240C77 254 72 272 56 272Z',
    fairway: 'M32 110C24 90 36 64 60 60C84 56 104 70 104 92C104 112 86 124 64 126C48 127 37 122 32 110Z',
    green: { cx: 67, cy: 90, rx: 24, ry: 17, rot: -12 },
    bunkers: [
      'M93 64C90 59 93 53 99 54C103 55 104 62 101 66C99 68 95 68 93 64Z',
      'M27 116C24 111 27 105 32 106C36 107 37 113 34 117C32 119 29 119 27 116Z',
    ],
    water: 'M14 208C9 190 20 168 43 164C62 161 79 150 98 156C112 161 113 181 105 196C97 210 75 215 56 217C38 219 18 222 14 208Z',
    waves: ['M30 192q5 -4 10 0t10 0t10 0', 'M54 178q5 -4 10 0t10 0t10 0', 'M60 203q5 -4 10 0t10 0'],
    tee: { x: 49.5, y: 250, w: 13, h: 7, rot: 5 },
    pin: [73, 84],
    spots: { 4: [56, 253.5], 5: [68.5, 89.5], 6: [73, 84] },
  },
];
