Basic Fetching in Client Components (useQuery)
To fetch data on the client side (e.g., customer queries, bookings, or documents), use the useQuery hook.

Mutating Data & Auto-invalidating (useMutation & queryClient)
To create, update, or delete data and automatically trigger a refetch of existing queries:

Server-Side Prefetching & Hydration (Next.js Server Components)
If you want to fetch data on the server for SEO or faster initial loads, and then hydrate it so that client-side hooks (useQuery) can pick it up instantly: