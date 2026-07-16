import { defineRelations } from "drizzle-orm";
import { account, session, user, verification, document } from "./schema";

export const authRelations = defineRelations(
  { user, session, account, verification, document },
  (r) => ({
    user: {
      sessions: r.many.session(),
      accounts: r.many.account(),
      documents: r.many.document(),
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
  }),
);

