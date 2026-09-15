-- 이미 만들어둔 Supabase 프로젝트(20260915_ETNS_S)에 로그인 기능을 추가할 때 실행하세요.
-- SQL Editor에 붙여넣고 Run 하면 됩니다.

create table if not exists users (
  id bigint generated always as identity primary key,
  email text unique not null,
  password_hash text not null
);

alter table users enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies where tablename = 'users' and policyname = 'public access for demo'
  ) then
    create policy "public access for demo" on users for all using (true) with check (true);
  end if;
end $$;

-- todos 테이블에 소유자(user_id) 컬럼 추가
-- 참고: 테스트하면서 만든 항목은 모두 지워둬서 현재 todos 테이블은 비어있을 것으로 예상합니다.
-- 혹시 남아있는 데이터가 있다면 user_id가 없어 화면에 보이지 않게 되니, 필요하면 먼저 비워주세요.
alter table todos add column if not exists user_id bigint references users (id) on delete cascade;
