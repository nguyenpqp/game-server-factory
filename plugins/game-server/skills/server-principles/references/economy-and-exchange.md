# Economy and exchange

Read this note when currency or items are bought, sold, sent, or traded, such as a shop with limits, rotating offers, mail with attachments, gifts between players, trades, or a real money purchase.

## Questions for the design

- For each offer: what it costs, what it gives, how many a player may buy per period, and when the limit resets, in which time zone.
- Is any offer limited across the whole server?
- For rotating offers: how are they picked for each player, when do they change, and can a player pay to change them early?
- Is there a maximum balance for each currency, or a bag size, and what happens to an amount past it?
- For mail and gifts: who may send to whom, how many per day, when an attachment expires, and what happens when the mailbox is full.
- Can a player refuse or return a gift?
- For trades: do both players confirm, and what happens when an offered item changes before both confirm?
- For a real money purchase: what it gives, any first purchase bonus, and what happens on a refund or a chargeback.

## Traps

### Server authority and anti-cheat

- The request carries a price, an amount granted, or a discount. The server takes them from config.
- The request buys an offer that is not on the player's current list, or not open now.
- A quantity times a price overflows its type.
- The cost is taken before every cost is checked, or a grant that throws keeps the cost.
- A grant past a balance cap, into a full bag, or into a full mailbox drops the value, or throws after the cost was taken.
- A retried purchase or claim buys or grants twice.
- The purchase limit resets by the JVM's zone, or by a timer in memory. The limit and its reset come from stored times and server time.
- A player floods gifts or mail to other players.
- A store receipt that the client sends is accepted again, on the same account or on another one. The server checks the receipt with the store and remembers its transaction id.

### Config

- Prices, limits, offers, and their windows are in code. Each offer is a row with an id, and each cost and grant is one record in the shared cost-and-reward shape.
- An offer that is not for sale is written as a zero price, so it sells for free.
- Stored purchase counts refer to an offer by list position.
- Store product ids and payment secrets sit in the balance file. They go to environment config.

### Modularity

- The shop or the mail feature changes inventory by importing it. It grants through the inventory contract.
- Every feature that sends rewards by mail builds the mail by hand. Mail offers a contract, and senders call it.

### Multi-node and rollout

- A gift or a trade loads and saves the other player's document. The other player receives through the durable inbox, applied once by their owner.
- The sender pays, and the delivery fails. Take the sender's cost first, and refund it only when the delivery definitely failed. An unknown result is logged for repair and not refunded.
- A claim mark and the attachment it grants are saved apart.
- A crash or a retry at any step of a trade loses or duplicates either side's items.
- A trade goes through after one side's item changed, after both confirmed.
- A server-wide stock is counted in node memory, or by a read and a write, so it sells more than its stock. A failed stock check reads as "sold out" or as "bought".
- Every active player writes one stock counter. A sharded counter can no longer hold an exact limit, so the design must allow that.
- A mailbox or a purchase history grows without a cap.
- A payment callback grants directly, or twice. It checks the signature, the product, and the price, locks on the transaction id, and delivers through the inbox.
- A refund or a chargeback callback has no path, or takes the value back twice.

### Tests and metrics

- Each limit reset and each window edge has a test with injected time.
- Each replayed purchase and each duplicate callback grants once.
- Every cost and grant is logged with its amount, its reason, and the trace id.
