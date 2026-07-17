import { defineRelations } from "drizzle-orm";
import { account, session, user, verification, document, query, booking } from "./schema";

export const authRelations = defineRelations(
  { user, session, account, verification, document, query, booking },
  (r) => ({
    user: {
      sessions: r.many.session(),
      accounts: r.many.account(),
      documents: r.many.document(),
      queries: r.many.query(),
      bookings: r.many.booking(),
    },
    session: {
      user: r.one.user({
        from: [r.session.userId],
        to: [r.user.id],
      }),
    },
    account: {
      user: r.one.user({
        from: [r.account.userId],
        to: [r.user.id],
      }),
    },
    document: {
      user: r.one.user({
        from: [r.document.userId],
        to: [r.user.id],
      }),
    },
    query: {
      user: r.one.user({
        from: [r.query.userId],
        to: [r.user.id],
      }),
    },
    booking: {
      user: r.one.user({
        from: [r.booking.userId],
        to: [r.user.id],
      }),
    },
  }),
);


