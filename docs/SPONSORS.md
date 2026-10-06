# Sponsoring the Atlas

Read this file on the GitHub website, not in a text editor, so the boxes and links show
properly.

This file has two parts:

1. **Profile text to paste** into GitHub Sponsors.
2. **How to switch it on**: step-by-step instructions for the owner.

GitHub Sponsors is the only fundraising channel for this project (see "Decisions recorded on
6 Oct 2026" in `PQ_ATTEST_BRIEF.md`). There is no token, coin, staking or sale of anything.

## Part 1. Profile text to paste

Open this file on GitHub. Each grey box has a copy icon at its top right. Click it, then
paste into the matching box in GitHub Sponsors. Do not retype anything.

Keep these rules, now and later:

- Quote no exposure figures (ETH amounts, shares, token values or organisation results)
  until they are published from a file in `data/snapshots/`. Then give the snapshot date
  beside each figure.
- Describe the status as it is. When the first snapshot is published, rewrite the
  "Where it stands" paragraph.
- Never offer tokens, coins, a share of anything, or any financial return.

### Short bio

```text
I am building the Ethereum Quantum Exposure Atlas: open code for a reproducible measurement of how much value on Ethereum a future quantum computer could put at risk.
```

### Introduction

```text
**What this is.** Every Ethereum account that has sent a transaction has revealed its public key. A large enough quantum computer could use that key to work out the private key and move the funds. The widely quoted estimate of how much ETH is exposed this way rests on a 2021 scan, with no public re-measurement as of June 2026.

The Ethereum Quantum Exposure Atlas is built to re-measure it from public blockchain data, with open code that anyone can re-run and check. It will also measure a surface that a September 2026 survey listed as not yet measured: token value that can still be moved by an old-style `permit` signature after an account moves to a quantum-safe key. A separate module will report, for each named organisation, which keys control its contracts and whether those keys are exposed.

**Where it stands.** The code is written and unit-tested offline. It has not yet run on live data, so there are no published figures yet. Please sponsor the work to come, not results that already exist.

**What your sponsorship pays for.** The project is designed to run on free tiers only (BigQuery's free monthly allowance, public RPC endpoints, GitHub Pages), so your money buys time, not services:

- finishing the work: the first live run, the per-organisation reports, a free public dashboard, and signed attestations on a testnet;
- refreshing the measurement and publishing every snapshot with its data;
- keeping the dashboard free for everyone, with no trackers.

**What it does not buy.** There is no token, coin, staking or sale. Sponsors get no financial return.

**Independence.** Sponsors have no say over the method, the results, or which organisations are reported and when. Sponsorship gives no early access to results, method changes or organisation reports. (Every organisation named in a report is told about its own page before it is published, sponsor or not.) If a sponsor is also an organisation in the report registry, its report will say so.

Code, method and limits: https://github.com/kalyogyogi-ui/eth-quantum-exposure-atlas (MIT licence).
```

### Featured work

Pick this repository, `eth-quantum-exposure-atlas`. Step 6 says how.

### Monthly tiers (US dollars)

Each grey box is the description for one tier. A published price cannot be changed later,
so check the price before you publish.

**$3 a month**

```text
**Supporter.** Thank you. Your support pays for time on the Atlas. It gives no say over the findings and no financial return.
```

**$10 a month**

```text
**Named supporter.** Everything above, and your name or GitHub username in the thanks list in the README, if you want it.
```

**$25 a month**

```text
**Methods reader.** Everything above, and a short note to sponsors each time a method change is published, sent on the same day the change appears in the public docs. Notes come by GitHub Sponsors email, if you keep sponsor updates on. They contain no figures and no organisation reports, and nothing in them is new or private.
```

**$50 a month**

```text
**Sustaining sponsor.** Everything above, and your name listed as a sustaining sponsor in the thanks list in the README. It gives no say over the findings and no financial return.
```

### One-time tier

**$15 once**

```text
**One-time thanks.** Thank you. Your support pays for time on the Atlas. It gives no say over the findings and no financial return.
```

No tier gives early or private access to results, method changes or organisation reports,
any say over the findings, or any financial return. Do not add a tier that does.

## Part 2. How to switch it on (for the owner)

These steps are taken from GitHub's own documentation (read on 6 Oct 2026). Screens can
change. If a button has a slightly different name, pick the closest one.

### Before you start, have ready

- Your GitHub login (username `kalyogyogi-ui`).
- A phone with a free authenticator app installed, for example Google Authenticator or
  Microsoft Authenticator (from the Play Store or App Store). It shows six-digit login
  codes.
- A bank account in India in your own name. GitHub says the country you live in and the
  country of your bank account must match.
- Your PAN card.
- About an hour, then a few days of waiting.

If you are under 18, a parent or guardian must also give their details to Stripe (the
payment company GitHub uses).

### Steps

1. **Check that India is supported.** Open
   https://docs.github.com/en/sponsors/getting-started-with-github-sponsors/about-github-sponsors#supported-regions-for-github-sponsors
   and look for "India" in the list. On 6 Oct 2026 the source of that page listed India. If
   India is missing, stop here and read "If GitHub Sponsors does not work for you" below.

2. **Turn on two-factor authentication (2FA).** GitHub requires it before you can be
   sponsored. Skip this step if it is already on.
   1. Click your profile picture (top right), then **Settings**.
   2. In the left menu, under "Access", click **Password and authentication**.
   3. Under "Two-factor authentication", click **Enable two-factor authentication**.
   4. Open the authenticator app on your phone, tap **+** (add an account), and point the
      camera at the square code on the screen.
   5. Type the six-digit code that the app shows.
   6. Under "Save your recovery codes", click **Download**. Keep that file safe and
      private: it is how you get back in if you lose your phone.
   7. Click **I have saved my recovery codes**.

3. **Apply.**
   1. Go to https://github.com/sponsors and click **Get sponsored** (it may say
      **Join the waitlist** instead).
   2. Fill in your contact details with your real name. GitHub requires your true identity.
   3. When asked how to be paid, choose **bank account**. (A "fiscal host" is an outside
      organisation that holds money for projects. This project does not have one.)
   4. Read the GitHub Sponsors Additional Terms and the Privacy Statement, then click
      **Submit**.

4. **Open your Sponsors dashboard.** Click your profile picture (top right), then
   **Your sponsors**. If you see a list, click **Dashboard** next to your account. If GitHub
   says your application is still being reviewed, wait a day or two and try again. GitHub
   may also contact you for more information.

5. **Put the latest work on the main branch.** The profile text links to the repository,
   and visitors see its main branch. Main still shows older work (for example, no
   per-organisation module). The newer work is waiting in pull request #1.
   1. Open https://github.com/kalyogyogi-ui/eth-quantum-exposure-atlas/pull/1. If it says
      the pull request is already merged, go to step 6.
   2. Scroll to the bottom, click **Merge pull request**, then **Confirm merge**.
   3. Do not delete the branch afterwards.

   This moves all the work in pull request #1 into main. It does not switch on the Sponsor
   button; that comes later, in step 11. If the merge button is grey or GitHub shows a
   warning, do not force it: ask Claude for help. If you are not ready to merge yet, stop
   here and come back when it is merged.

6. **Paste the profile.** In the dashboard, in the left menu, click **Profile details**.
   1. Copy the short bio box from Part 1 and paste it into **Short bio**.
   2. Copy the introduction box from Part 1 and paste it into **Introduction**.
   3. Under **Featured work**, click **Edit**. In the box that opens, tick
      `eth-quantum-exposure-atlas`, then click **Save**.
   4. Click **Update profile**.

7. **Add the tiers.** In the dashboard, in the left menu, click **Sponsor tiers**.
   1. If GitHub first shows suggested example tiers, click **Skip this step**.
   2. Optionally, in the "Custom amounts" section, type a low minimum amount, for example
      1 (US dollars). It applies to both monthly and one-time sponsorships. You may also
      leave these boxes empty.
   3. Click **Add a monthly tier** (at the right of the page), type the price, and paste
      that tier's description box from Part 1.
   4. Click **Save draft**. Read it through, then click **Publish tier**.
   5. Repeat for each monthly tier. For the one-time tier, click **One-time tiers**, then
      **Add a one-time tier**, and do the same.

8. **Add your bank details.** In the dashboard, click **Stripe Connect account** and follow
   the steps. Type your name and date of birth exactly as on your PAN card. GitHub warns they
   are hard to change after you submit.

9. **Fill in the tax form.** In the dashboard, click **Overview**, then the **tax forms**
   link. The form for a person living outside the United States is **W-8BEN**. In the
   "Foreign tax identifying number" box, type your PAN. Sign and submit it. Stripe keeps the
   form; you do not send it to the US tax office.

10. **Ask for approval.** In the dashboard, click **Request approval**. GitHub says a review
    may take a few days. Once approved, your page goes live by itself at
    https://github.com/sponsors/kalyogyogi-ui. Open that link to check. Once it opens, ask
    Claude: "My GitHub Sponsors page is live. Please remove the words *(this link works
    only after the owner has applied and GitHub has approved the profile)* from the
    README."

11. **Turn on the Sponsor button on the repository.** Do this only after step 10 is
    approved.
    1. **Add the button file.** The button needs a small file, `.github/FUNDING.yml`, on
       the main branch. It is not in pull request #1 on purpose, so that it reaches main
       only after you are approved. Ask Claude: "My GitHub Sponsors page is approved.
       Please open a small pull request that adds only `.github/FUNDING.yml`, containing
       the line `github: kalyogyogi-ui`." Claude will give you a link to that pull
       request. Open it, scroll to the bottom, click **Merge pull request**, then
       **Confirm merge**.
    2. **Tick the setting.** Open
       https://github.com/kalyogyogi-ui/eth-quantum-exposure-atlas and click **Settings**
       (under the repository name; if you cannot see it, click **...** first). On the
       "General" page, find "Features" and tick **Sponsorships**. If the Sponsor button
       does not appear in 11.3, come back here. In the "Sponsorships" box, click
       **Set up sponsor button** (or **Override funding links**), check that the file says
       `github: kalyogyogi-ui`, and click **Commit changes** to the main branch.
    3. **Check.** Open the repository's main page and look for a **Sponsor** button. If it
       is not there, check that the merge in 11.1 finished and the box in 11.2 is ticked,
       then reload the page.

12. **Keep it honest.**
    - When someone picks the $10 or $50 tier and wants their name shown, ask Claude to add
      their name under "Thanks to sponsors" in `README.md`.
    - When a new sponsor looks like a company or project, ask Claude to check whether it
      is in `orgs/registry.yaml`, and to note it in that organisation's report if so.
    - Notes for the $25 and $50 tiers: send a note only after the method change is already
      in the public docs. In the dashboard's left menu, under "Manage", click
      **Newsletters**, then **Draft a new update**. Click the **All sponsors** menu and pick
      the $25 and $50 tiers (both get these notes). Type a subject and the note, then click
      **Publish**.
    - When the first snapshot is published, ask Claude to rewrite the "Where it stands"
      paragraph, then paste the new introduction into **Profile details**.

### Good to know

- **Fees.** GitHub takes no fee on sponsorships from personal accounts. Sponsorships from
  organisation accounts carry a fee of up to 6%.
- **Timing.** Stripe sends the first payment about 60 days after the first sponsorship
  starts; it can take a few more days to reach your bank. After that, payouts are usually
  monthly (around the 22nd), but dates can vary by country and a minimum payout amount may
  apply. Amounts are set in US dollars and may be converted to rupees.
- **Taxes.** GitHub does not take tax out of payments (unless the law requires it). You are
  responsible for your own taxes. Before your first payment, find out how Indian income tax
  and GST apply. The Income Tax Department's website (incometax.gov.in) has free help; a
  chartered accountant can also advise, usually for a fee. This was not checked here.
- **No matching.** GitHub's matching fund closed to new applicants on 1 January 2020.
  GitHub does not add money.
- **Approval is not guaranteed.** GitHub can refuse an application.

### If GitHub Sponsors does not work for you

If India is not listed, your application is refused, or you cannot finish the bank or tax
steps:

- Do not do step 11. If `.github/FUNDING.yml` was already added, ask Claude to remove it,
  and untick **Sponsorships** in Settings. GitHub does not document what the Sponsor
  button shows for an account that is not approved.
- Ask Claude to remove the GitHub Sponsors link from the README and change the
  "Support this project" section, so it does not point to a page that does not work.
- If GitHub offers a waitlist, you can join it and try again later.
- Do not switch to paid services, other funding sites, or a crypto wallet address for
  donations. Any other channel is a new decision and must be recorded in
  `PQ_ATTEST_BRIEF.md` first.

### Not checked

- The live docs.github.com pages could not be opened from the session that wrote this file.
  The steps come from the source files those pages are built from, in GitHub's public
  `github/docs` repository.
- What the Sponsor button or the sponsors link shows before GitHub approves you is not
  documented. That is why `.github/FUNDING.yml` is kept out of pull request #1 and added
  only after approval (step 11). The README link to the sponsors page reaches main with
  pull request #1, with a note that it works only after approval.
- GitHub's docs do not say whether the button shows without the **Sponsorships** box. Tick
  it either way.
- GitHub's docs do not say what happens if the "Custom amounts" boxes are left empty.
- What Stripe asks a person in India for (ID, bank codes, other forms) and the smallest
  payout in rupees were not checked. Follow Stripe's own screens.
- How Indian tax applies to sponsorship money was not checked.
