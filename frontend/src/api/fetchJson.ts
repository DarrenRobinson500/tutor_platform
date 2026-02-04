export async function FetchJson(
  url: string,
  options: RequestInit = {},
  setLoading?: (v: boolean) => void,
  setError?: (v: string | null) => void
) {
  if (setLoading) setLoading(true);
  if (setError) setError(null);

  try {
    const res = await fetch(url, options);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || res.statusText);
    }
    return await res.json();
  } catch (err: any) {
    if (setError) setError(err.message);
    throw err;
  } finally {
    if (setLoading) setLoading(false);
  }
}