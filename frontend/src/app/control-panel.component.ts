import { Component, inject } from '@angular/core';
import { ButtonModule } from '@progress/kendo-angular-buttons';
import { KENDO_SWITCH } from '@progress/kendo-angular-inputs';
import { EngineDataService } from './engine-data.service';
import { getElectronIpc } from './electron-bridge';

@Component({
  selector: 'app-control-panel',
  imports: [KENDO_SWITCH, ButtonModule],
  host: {
    class: 'control-panel',
    '(mouseenter)': 'onMouseEnter()',
    '(mouseleave)': 'onMouseLeave()',
  },
  template: `
    <h3>Chess Analyzer</h3>
    <div class="status-row">
      <span class="status-dot" [class.active]="data.activeTurn() === 'w'" [class.black]="data.activeTurn() === 'b'"></span>
      <span class="status-text">{{ data.activeTurn() === 'w' ? 'White to move' : 'Black to move' }}</span>
    </div>
    <div class="turn-actions" role="group" aria-label="Side to move">
      <button kendoButton [class.selected]="data.activeTurn() === 'w'" [attr.aria-pressed]="data.activeTurn() === 'w'" (click)="setTurn('w')">White turn</button>
      <button kendoButton [class.selected]="data.activeTurn() === 'b'" [attr.aria-pressed]="data.activeTurn() === 'b'" (click)="setTurn('b')">Black turn</button>
    </div>
    <label>
      <span>Auto analyze</span>
      <kendo-switch [checked]="data.autoAnalyze()" (valueChange)="setAutoAnalyze($event)"></kendo-switch>
    </label>
    <label>
      <span>Show best move</span>
      <kendo-switch [checked]="data.showBest()" (valueChange)="data.showBest.set($event)"></kendo-switch>
    </label>
    <label>
      <span>Show alternatives</span>
      <kendo-switch [checked]="data.showAlts()" (valueChange)="data.showAlts.set($event)"></kendo-switch>
    </label>
    <label>
      <span>Show threats</span>
      <kendo-switch [checked]="data.showThreats()" (valueChange)="data.showThreats.set($event)"></kendo-switch>
    </label>
    <label>
      <span>Blunder warnings</span>
      <kendo-switch [checked]="data.showBlunders()" (valueChange)="data.showBlunders.set($event)"></kendo-switch>
    </label>
    <label>
      <span>Eval bar</span>
      <kendo-switch [checked]="data.showEvalBar()" (valueChange)="data.showEvalBar.set($event)"></kendo-switch>
    </label>
    <div class="eval-row">
      <div class="eval">{{ data.evalText() }}</div>
      <div class="depth" [class.active]="data.depth() > 0">d{{ data.depth() }}</div>
    </div>
    <label>
      <span>Flip board</span>
      <kendo-switch [checked]="data.isFlipped()" (valueChange)="data.sendCommand('set_flipped', $event)"></kendo-switch>
    </label>

    <div class="actions">
      <button kendoButton (click)="calibrate()">Calibrate</button>
      <button kendoButton (click)="captureTemplates()">Capture Templates</button>
      <button kendoButton (click)="toggleOverlay()">Hide/Show</button>
      <button kendoButton (click)="analyzeNow()" class="analyze-now" themeColor="primary" [disabled]="data.isAnalyzing()">
        {{ data.isAnalyzing() ? data.analysisLabel() : 'Analyze now' }}
      </button>
      @if (data.isAnalyzing()) {
        <div class="analysis-status" role="status" aria-live="polite">
          <span>{{ data.analysisLabel() }}</span>
          <span class="analysis-progress" aria-hidden="true"><span></span></span>
        </div>
      }
    </div>

    <div class="legend">
      <div class="legend-title">Arrow colors</div>
      <div class="legend-row"><span class="dot best"></span> Best move</div>
      <div class="legend-row"><span class="dot alt1"></span> 1st alternative</div>
      <div class="legend-row"><span class="dot alt2"></span> 2nd alternative</div>
      <div class="legend-row"><span class="dot threat"></span> Threat</div>
    </div>
  `,
})
export class ControlPanelComponent {
  protected readonly data = inject(EngineDataService);

  calibrate(): void {
    this.data.sendCommand('calibrate');
  }

  captureTemplates(): void {
    this.data.sendCommand('capture_templates');
  }

  setTurn(turn: 'w' | 'b'): void {
    this.data.sendCommand('set_turn', turn);
  }

  setAutoAnalyze(value: boolean): void {
    this.data.sendCommand('set_auto_analyze', value);
  }

  analyzeNow(): void {
    this.data.requestAnalysis();
  }

  toggleOverlay(): void {
    getElectronIpc()?.send('toggle-overlay');
  }

  onMouseEnter(): void {
    this.setIgnoreMouseEvents(false);
  }

  onMouseLeave(): void {
    this.setIgnoreMouseEvents(true);
  }

  private setIgnoreMouseEvents(ignore: boolean): void {
    getElectronIpc()?.send('set-ignore-mouse-events', ignore);
  }
}
