// Configuration ESLint volontairement permissive pour un premier passage sur
// un code jamais linté (~10k lignes TS accumulées au fil des sessions).
// Objectif : attraper les vraies erreurs (variables/imports inconnus) sans
// noyer le résultat sous des règles de style. À durcir une fois nettoyé.
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["dist/**", "node_modules/**", "public/**"],
  },
  ...tseslint.configs.recommended,
  {
    rules: {
      // Le code utilise beaucoup `any` pour les payloads WebSocket dynamiques
      // et les API DOM non typées — pas une erreur dans ce contexte.
      "@typescript-eslint/no-explicit-any": "off",
      // Variables déclarées mais pas encore branchées (travail itératif) —
      // avertissement plutôt que blocage.
      "@typescript-eslint/no-unused-vars": "warn",
      "@typescript-eslint/no-empty-object-type": "off",
    },
  }
);
