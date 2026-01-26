export interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
}

export interface Source {
  title: string;
  source: string;
  url: string;
  date: string;
}
