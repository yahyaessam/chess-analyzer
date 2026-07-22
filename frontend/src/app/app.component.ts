import { Component, inject } from '@angular/core';
import { ControlPanelComponent } from './control-panel.component';
import { EngineDataService } from './engine-data.service';
import { getElectronIpc } from './electron-bridge';
import { OverlaySvgComponent } from './overlay-svg.component';

@Component({
  selector: 'app-root',
  imports: [OverlaySvgComponent, ControlPanelComponent],
  host: { class: 'app-root' },
  template: `<app-overlay-svg /><app-control-panel />`,
})
export class AppComponent {
  private readonly data = inject(EngineDataService);

  constructor() {
    const ipc = getElectronIpc();
    if (!ipc) {
      console.log('Electron IPC not available (running in browser?)');
      return;
    }
    ipc.on('calibrate', () => {
      console.log('Renderer: calibrate IPC received');
      this.data.sendCommand('calibrate');
    });
  }
}
