export { };

declare global {
  interface Window {
    electron?: {
      executeCommand: (command: string) => Promise<any>;
      getContext: () => Promise<any>;
      onStartRecording: (callback: () => void) => void;
      onToggleRecording: (callback: () => void) => void;
      showSummary: (content: string) => Promise<any>;
      onUpdateSummary: (callback: (content: string) => void) => void;
      resizeWindow: (width: number, height: number) => Promise<any>;
      stopExecution: () => Promise<any>;
      getTasks: () => Promise<any>;
      onWindowShow: (callback: (data?: { activeApp: string }) => void) => void;
      onWindowHide: (callback: () => void) => void;
      hideWindow: () => Promise<any>;
      getMemoryStatus: () => Promise<any>;
      clearMemory: () => Promise<any>;
      getPresets: () => Promise<any[]>;
      savePreset: (preset: any) => Promise<void>;
      deletePreset: (id: string) => Promise<void>;
      executePreset: (steps: any[], history: any[]) => Promise<any>;
      setApiKey: (key: string) => Promise<any>;
      getApiKey: () => Promise<string | null>;
      showAutomationOverlay: (show: boolean) => Promise<void>;
    };
  }
}
