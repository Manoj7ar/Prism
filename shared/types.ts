export interface Task {
  action: 'read_files' | 'browser_navigate' | 'browser_extract' | 'create_document' | 'send_email' | 'type_text' | 'press_keys' | 'open_app';
  params: Record<string, any>;
  description: string;
}

export interface CommandPlan {
  intent: string;
  tasks: Task[];
}

export interface ExecutionResult {
  success: boolean;
  message?: string;
  results?: any[];
  error?: string;
  intent?: string;
  tasks?: Task[];
}

export interface SystemContext {
  selected_files: string[];
  active_window: string;
  clipboard: string;
  browser_tab: {
    url: string | null;
    title: string | null;
  };
}
