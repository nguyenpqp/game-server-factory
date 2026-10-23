# Economy and exchange

Read this note when currency or items are bought, sold, sent, or traded, such as a shop with limits, rotating offers, mail with attachments, gifts between players, trades, or a real money purchase. How to use it is in the [genre notes index](index.md). Rule ids refer to the [rule index](../index.md).

## Questions for the design

- For each offer: what it costs, what it gives, how many a player may buy per period, and when the limit resets, in which time zone.
- Is any offer limited across the whole server?
- For rotating offers: how are they picked for each player, when do they change, and can a player pay to change them early?
- Is there a maximum balance for each currency, and what happens to an amount past it?
- For mail and gifts: who may send to whom, how many per day, when an attachment expires, and what happens when the mailbox is full.
- Can a player refuse or return a gift?
- For trades: do both players confirm, and what happens when an offered item changes before both confirm?
- For a real money purchase: what it gives, any first purchase bonus, and what happens on a refund or a chargeback.

## Traps

### Server authority and anti-cheat

- The request carries a price, an amount granted, or a discount. The server takes them from config (AUTH-01).
- The request buys an offer that is not on the player's current list, or not open now (AUTH-05, AUTH-06).
- A quantity times a price overflows its type (AUTH-04).
- The cost is taken before every cost is checked, or a grant that throws keeps the cost (AUTH-07).
- A retried purchase or claim buys or grants twice (AUTH-08).
- The purchase limit resets by the JVM's zone, or by a timer in memory. It is a stored count for a period that server time names, in the zone that CAP-CLOCK gives (AUTH-02, MN-11).
- A player floods gifts or mail to other players (AUTH-09).

### Config

- Prices, limits, offers, and their windows are in code (CFG-04, CFG-05). Each offer is a row with an id, and each cost and grant is one `{id, amount}` record (CFG-09, CFG-10).
- An offer that is not for sale is a zero price instead of an omitted key (CFG-10).
- Stored purchase counts refer to an offer by list position (CFG-06).
- Store product ids and payment secrets sit in the balance file. They go to environment config (CFG-07).

### Modularity

- The shop or the mail feature changes inventory by importing it. It grants through the inventory contract (MOD-01, MOD-02).
- Every feature that sends rewards by mail builds the mail by hand. Mail offers a contract, and senders call it (MOD-02).

### Multi-node and rollout

- A gift or a trade loads and saves the other player's document. The other player receives through the durable inbox, applied once by their owner (MN-02, MN-03).
- The sender pays, and the delivery fails. Take the sender's cost first, and refund it only when the delivery definitely failed. An unknown result is neither (AUTH-07, MN-13).
- A claim mark and the attachment it grants are saved apart (MN-12).
- A trade holds both sides' items in one player's state. Items in escrow live in shared state that changes in one atomic step (MN-05).
- A server-wide stock counter is one hot key (MN-05, PERF-08).
- A mailbox or a purchase history grows without a cap (PERF-06).
- A payment callback grants directly, or twice. It checks the signature, the product, and the price, locks on the transaction id, and delivers through the inbox (HTTP-02, HTTP-04, HTTP-05, HTTP-06).

### Tests and metrics

- Each limit reset and each window edge has a test with injected time (TEST-02).
- Each replayed purchase and each duplicate callback grants once (TEST-09).
- Every cost and grant is logged with its amount, its reason, and the trace id (MET-03, MET-04).
