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
      <button kendoButton (click)="analyzeNow()" class="analyze-now" themeColor="primary">Analyze now</button>
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

  analyzeNow(): void {
    this.data.sendCommand('analyze');
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
