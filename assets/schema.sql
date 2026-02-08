create table public.news (
  id uuid primary key default gen_random_uuid(),
  author_id uuid not null references auth.users(id) on delete cascade,
  title text not null,
  content text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger set_news_updated_at
before update on public.news
for each row
execute procedure public.set_updated_at();

create policy "Public can read news"
on public.news
for select
using (true);

create policy "Users can insert their own news"
on public.news
for insert
with check (auth.uid() = author_id);

create policy "Users can update their own news"
on public.news
for update
using (auth.uid() = author_id);

create policy "Users can delete their own news"
on public.news
for delete
using (auth.uid() = author_id);