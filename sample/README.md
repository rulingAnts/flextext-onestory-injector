# `sample/` — put real test data here, locally

Git-ignored except for this file. Drop a **copy** of a `.onestory` project and a
`.flextext` export here to develop against.

Never commit either. A `.onestory` carries the team's names, emails and stored
`HgPassword` values alongside unpublished language data; one was committed to a
sibling repo once and had to be purged from the entire history.

**Always work on a copy.** This tool writes into a project file in place, and a
tool under development should never be pointed at the only copy of anything.
