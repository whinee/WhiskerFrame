# Proposed Deny Diff: Raw Git Push

```diff
--- a/.config/agent-policy/settings.json (mock)
+++ b/.config/agent-policy/settings.json (mock)
@@ -10,2 +10,3 @@
     "deny": [
+      "git push",
+      "git push origin *"
     ],
     "allow": [
+      "~/.config/agent-policy/bin/agent-push"
     ]
```
