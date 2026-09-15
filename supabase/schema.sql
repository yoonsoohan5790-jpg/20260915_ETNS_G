-- Supabase SQL Editor에서 실행하세요.
-- ETNS 할 일 관리 앱용 테이블 생성 (로그인 기능 포함, 새로 만드는 경우)

create table if not exists users (
  id bigint generated always as identity primary key,
  email text unique not null,
  password_hash text not null
);

create table if not exists todos (
  id bigint generated always as identity primary key,
  user_id bigint not null references users (id) on delete cascade,
  title text not null,
  done boolean not null default false,
  created_at text not null
);

-- Row Level Security 활성화 + 데모용 전체 허용 정책
-- (교육용 데모 앱이라 Supabase 자체 인증 대신 앱에서 직접 로그인/비밀번호를 확인합니다.
--  사용자별 데이터 구분은 앱 코드가 user_id로 걸러서 처리하고, DB의 RLS는 데모 편의상 열어둔 것입니다.
--  실제 서비스라면 Supabase Auth 등을 도입해 RLS로도 이중 보호하는 것이 좋습니다.)
alter table users enable row level security;
alter table todos enable row level security;

create policy "public access for demo" on users for all using (true) with check (true);
create policy "public access for demo" on todos for all using (true) with check (true);
