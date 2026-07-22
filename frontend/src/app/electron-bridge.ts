export interface IpcRendererLike {
  send(channel: string, ...args: unknown[]): void;
  on(channel: string, listener: (...args: unknown[]) => void): void;
}

export function getElectronIpc(): IpcRendererLike | undefined {
  if (typeof window === 'undefined') {
    return undefined;
  }

  const win = window as unknown as { require?: (module: string) => unknown };
  if (typeof win.require !== 'function') {
    return undefined;
  }

  const electron = win.require('electron') as { ipcRenderer?: IpcRendererLike };
  return electron.ipcRenderer;
}
