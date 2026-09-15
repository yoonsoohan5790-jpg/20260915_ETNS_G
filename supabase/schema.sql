-- Supabase SQL Editor에서 실행하세요.
-- ETNS 할 일 관리 앱용 테이블 생성

create table if not exists todos (
  id bigint generated always as identity primary key,
  title text not null,
  done boolean not null default false,
  created_at text not null
);

-- Row Level Security 활성화 + 데모용 전체 허용 정책
-- (교육용 데모 앱이라 인증 없이 anon key로 접근합니다. 실제 서비스에서는 인증 기반 정책으로 교체해야 합니다.)
alter table todos enable row level security;

create policy "public access for demo"
  on todos
  for all
  using (true)
  with check (true);
