-- Retire les 5 scores de test du 26 octobre (classement « Combien ? »), et seulement eux.
DELETE FROM app.score s USING (VALUES
  ('Eliaslebg', 47920, '2026-10-26T20:19:55.377078+01:00'::timestamptz),
  ('Eliaslebg', 33200, '2026-10-26T19:56:26.848363+01:00'::timestamptz),
  ('Lohan', 9760, '2026-10-26T19:51:57.712859+01:00'::timestamptz),
  ('Lohan', 5800, '2026-10-26T19:54:10.783250+01:00'::timestamptz),
  ('Yanis', 620, '2026-10-26T18:46:55.221964+01:00'::timestamptz)
) AS v(name, score, created_at)
WHERE s.game = 'guess_count' AND s.name = v.name AND s.score = v.score AND s.created_at = v.created_at;
