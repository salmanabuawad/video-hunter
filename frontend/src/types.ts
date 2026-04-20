export interface Session {
  user_id: number;
  user_name: string;
  user_role: 'admin' | 'user' | 'readonly' | string;
  token: string;
}

export interface Project {
  id: number;
  name: string;
  subject: string;
  owner_id: number;
  created_at: string;
  updated_at: string;
}

export interface VideoRow {
  id: number;
  project_id: number;
  search_id: number;
  provider: 'youtube' | 'facebook' | string;
  provider_video_id: string;
  title: string;
  channel: string;
  description: string;
  duration_sec: number;
  view_count: number;
  published_at: string;
  thumbnail_url: string;
  source_url: string;
  state: 'candidate' | 'keep' | 'rejected' | 'purged' | string;
  has_local_file: boolean;
  download_url: string | null;
  created_at: string;
}

export interface SearchBatch {
  search_id: number;
  project_id: number;
  provider: string;
  query: string;
  has_more: boolean;
  batch: VideoRow[];
}

export interface AppConfigStatus {
  youtube_configured: boolean;
  facebook_configured: boolean;
}
