import { Component, computed, inject } from '@angular/core';
import { EngineDataService, MoveData, ThreatData } from './engine-data.service';

interface ArrowModel {
  id: string;
  d: string;
  color: string;
  width: number;
  marker: string;
  dash: string;
  isThreat: boolean;
}

@Component({
  selector: 'app-overlay-svg',
  host: { class: 'overlay-svg' },
  styles: [
    `:host { position: fixed; inset: 0; pointer-events: none; }`,
    `svg { width: 100vw; height: 100vh; display: block; }`,
    `.threat-arrow { animation: dash 1s linear infinite; }`,
    `@keyframes dash { to { stroke-dashoffset: -15; } }`,
    `.arrow-glow { filter: drop-shadow(0 0 6px currentColor); }`,
    `.arrow-fade-in { animation: fadeIn 0.3s ease-out; }`,
    `@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }`,
  ],
  template: `
    <svg [attr.viewBox]="viewBox()">
      <defs>
        <marker id="m-best" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#00FF66" />
        </marker>
        <marker id="m-alt1" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#00E5FF" />
        </marker>
        <marker id="m-alt2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#FFC107" />
        </marker>
        <marker id="m-threat" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#FF1744" />
        </marker>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      @if (blunderSquare(); as sq) {
        <rect
          [attr.x]="sq.x - sqSize() / 2"
          [attr.y]="sq.y - sqSize() / 2"
          [attr.width]="sqSize()"
          [attr.height]="sqSize()"
          fill="#FF1744"
          fill-opacity="0.35"
          filter="url(#glow)" />
      }

      @for (arrow of arrows(); track arrow.id) {
        <path
          [attr.d]="arrow.d"
          [attr.stroke]="arrow.color"
          [attr.stroke-width]="arrow.width"
          [attr.stroke-dasharray]="arrow.dash"
          [attr.marker-end]="arrow.marker"
          fill="none"
          stroke-linecap="round"
          stroke-linejoin="round"
          [style.color]="arrow.color"
          class="arrow-glow arrow-fade-in"
          [class.threat-arrow]="arrow.isThreat" />
      }

      @if (data.showEvalBar()) {
        <g [attr.transform]="evalBarTransform()">
          <rect x="0" y="0" width="24" [attr.height]="bounds().h" fill="rgba(0,0,0,0.5)" rx="4" />
          <rect x="0" [attr.y]="evalBarY()" width="24" [attr.height]="evalBarHeight()" fill="#00FF66" rx="4" />
        </g>
      }
    </svg>
  `,
})
export class OverlaySvgComponent {
  protected readonly data = inject(EngineDataService);

  protected readonly width = computed(() => (typeof window !== 'undefined' ? window.innerWidth : 1920));
  protected readonly height = computed(() => (typeof window !== 'undefined' ? window.innerHeight : 1080));
  protected readonly dpr = computed(() => (typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1));

  protected readonly viewBox = computed(() => `0 0 ${this.width()} ${this.height()}`);

  protected readonly bounds = computed(() => {
    const b = this.data.boardBounds();
    const r = this.dpr();
    return { x: b.x / r, y: b.y / r, w: b.w / r, h: b.h / r };
  });

  protected readonly sqSize = computed(() => this.bounds().w / 8);

  protected readonly blunderSquare = computed(() => {
    if (!this.data.showBlunders() || !this.data.blunderAlert().is_blunder || !this.data.blunderAlert().square) {
      return null;
    }
    return this.squareCenter(this.data.blunderAlert().square!);
  });

  protected readonly arrows = computed(() => this.buildArrows());

  protected readonly evalBarY = computed(() => {
    const ev = this.data.evaluation();
    const h = this.bounds().h;
    let ratio: number;
    if (ev.type === 'cp') {
      const clamped = Math.max(-1000, Math.min(1000, ev.value));
      ratio = (clamped + 1000) / 2000;
    } else if (ev.value > 0) {
      ratio = 1;
    } else {
      ratio = 0;
    }
    const barHeight = h * ratio;
    return h - barHeight;
  });

  protected readonly evalBarHeight = computed(() => this.bounds().h - this.evalBarY());

  protected readonly evalBarTransform = computed(() => {
    const b = this.bounds();
    return `translate(${b.x + b.w + 16}, ${b.y})`;
  });

  protected squareCenter(algebraic: string): { x: number; y: number } {
    const file = algebraic.charCodeAt(0) - 'a'.charCodeAt(0);
    const rank = parseInt(algebraic[1], 10);
    const b = this.bounds();
    const s = this.sqSize();
    const flipped = this.data.isFlipped();
    const fileIndex = flipped ? 7 - file : file;
    const rankIndex = flipped ? rank - 1 : 8 - rank;
    return {
      x: b.x + (fileIndex + 0.5) * s,
      y: b.y + (rankIndex + 0.5) * s,
    };
  }

  private buildArrows(): ArrowModel[] {
    const arrows: ArrowModel[] = [];
    const moves = this.data.moves();

    if (this.data.showBest() && moves.best) {
      arrows.push(this.buildMoveArrow(moves.best, '#00FF66', 12, 'url(#m-best)', '', 'best'));
    }

    if (this.data.showAlts()) {
      if (moves.alt_1) {
        arrows.push(this.buildMoveArrow(moves.alt_1, '#00E5FF', 8, 'url(#m-alt1)', '', 'alt1'));
      }
      if (moves.alt_2) {
        arrows.push(this.buildMoveArrow(moves.alt_2, '#FFC107', 6, 'url(#m-alt2)', '', 'alt2'));
      }
    }

    if (this.data.showThreats()) {
      for (const threat of this.data.threats()) {
        arrows.push({
          id: `t-${threat.from}-${threat.to}`,
          d: this.arrowPath(threat.from, threat.to),
          color: '#FF1744',
          width: 7,
          marker: 'url(#m-threat)',
          dash: '8 6',
          isThreat: true,
        });
      }
    }

    return arrows;
  }

  private buildMoveArrow(
    move: MoveData,
    color: string,
    width: number,
    marker: string,
    dash: string,
    id: string
  ): ArrowModel {
    return {
      id: `${id}-${move.from}-${move.to}`,
      d: this.arrowPath(move.from, move.to),
      color,
      width,
      marker,
      dash,
      isThreat: false,
    };
  }

  private arrowPath(from: string, to: string): string {
    const a = this.squareCenter(from);
    const b = this.squareCenter(to);
    const s = this.sqSize();
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < 1) return `M ${a.x} ${a.y} L ${b.x} ${b.y}`;
    const offset = s * 0.3;
    const ux = dx / dist;
    const uy = dy / dist;
    const sx = a.x + ux * offset;
    const sy = a.y + uy * offset;
    const ex = b.x - ux * offset;
    const ey = b.y - uy * offset;
    const mx = (sx + ex) / 2;
    const my = (sy + ey) / 2;
    const curve = s * 0.15;
    const cx = mx + -uy * curve;
    const cy = my + ux * curve;
    return `M ${sx} ${sy} Q ${cx} ${cy} ${ex} ${ey}`;
  }
}
