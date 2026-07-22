import { PLATFORM_ID, Service, computed, inject, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

export interface Bounds {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface MoveData {
  from: string;
  to: string;
  pv_index: number;
  score: number;
}

export interface ThreatData {
  from: string;
  to: string;
  severity: string;
  type: string;
  score?: number;
}

export interface EvalData {
  type: 'cp' | 'mate';
  value: number;
}

export interface ServerPayload {
  timestamp: number;
  board_bounds: Bounds;
  active_turn: 'w' | 'b';
  is_flipped: boolean;
  evaluation: EvalData;
  depth: number;
  moves: {
    best: MoveData | null;
    alt_1: MoveData | null;
    alt_2: MoveData | null;
  };
  threats: ThreatData[];
  blunder_alert: {
    is_blunder: boolean;
    square: string | null;
  };
}

@Service()
export class EngineDataService {
  private readonly platformId = inject(PLATFORM_ID);
  private ws: WebSocket | undefined;
  private reconnectTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly pending: { action: string; value?: unknown }[] = [];

  readonly boardBounds = signal<Bounds>({ x: 0, y: 0, w: 0, h: 0 });
  readonly activeTurn = signal<'w' | 'b'>('w');
  readonly isFlipped = signal(false);
  readonly evaluation = signal<EvalData>({ type: 'cp', value: 0 });
  readonly depth = signal(0);
  readonly moves = signal<ServerPayload['moves']>({ best: null, alt_1: null, alt_2: null });
  readonly threats = signal<ThreatData[]>([]);
  readonly blunderAlert = signal<ServerPayload['blunder_alert']>({ is_blunder: false, square: null });

  readonly showBest = signal(true);
  readonly showAlts = signal(true);
  readonly showThreats = signal(true);
  readonly showBlunders = signal(true);
  readonly showEvalBar = signal(true);

  readonly evalText = computed(() => {
    const ev = this.evaluation();
    return ev.type === 'mate' ? `Mate ${ev.value}` : `${(ev.value / 100).toFixed(1)}`;
  });

  constructor() {
    if (isPlatformBrowser(this.platformId)) {
      this.connect();
    }
  }

  private connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.ws = new WebSocket('ws://127.0.0.1:8765');
    this.ws.onmessage = (event) => this.handleMessage(event.data as string);
    this.ws.onopen = () => {
      console.log('Connected to analyzer backend');
      this.flushPending();
    };
    this.ws.onerror = (error) => console.error('WebSocket error:', error);
    this.ws.onclose = () => {
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
      }
      this.reconnectTimer = setTimeout(() => this.connect(), 1000);
    };
  }

  private handleMessage(data: string): void {
    try {
      const payload = JSON.parse(data) as ServerPayload;
      this.boardBounds.set(payload.board_bounds);
      this.activeTurn.set(payload.active_turn);
      this.isFlipped.set(payload.is_flipped);
      this.evaluation.set(payload.evaluation);
      this.depth.set(payload.depth ?? 0);
      this.moves.set(payload.moves);
      this.threats.set(payload.threats);
      this.blunderAlert.set(payload.blunder_alert);
    } catch (error) {
      console.error('Failed to parse payload', error);
    }
  }

  sendCommand(action: string, value?: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action, value }));
      console.log('Sent command to backend:', action);
    } else {
      console.log('WebSocket not open, queueing command:', action, 'readyState:', this.ws?.readyState);
      this.pending.push({ action, value });
    }
  }

  private flushPending(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }
    while (this.pending.length) {
      const cmd = this.pending.shift();
      if (cmd) {
        this.ws.send(JSON.stringify(cmd));
        console.log('Sent queued command:', cmd.action);
      }
    }
  }
}
