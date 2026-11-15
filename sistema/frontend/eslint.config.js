import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

// GUIA_ESTILO_CODIGO.md: propiedades impuestas por bibliotecas externas
// (React/DOM, TanStack Query, Intl), la unica excepcion permitida a
// snake_case (Seccion 1), declarada aqui una sola vez -- nunca
// silenciada linea por linea.
const _PROPIEDADES_EXTERNAS =
  "^(className|classList|onClick|onChange|onInput|onSubmit|onBlur|onFocus|onKeyDown|onKeyUp|onMouseEnter|onMouseLeave|children|style|href|target|rel|type|value|defaultValue|placeholder|disabled|id|name|checked|htmlFor|src|alt|width|height|colSpan|rowSpan|tabIndex|autoFocus|autoComplete|maxLength|minLength|readOnly|required|min|max|step|role|isActive|queryKey|queryFn|mutationFn|onSuccess|onError|onSettled|refetchInterval|refetchOnWindowFocus|defaultOptions|enabled|retry|staleTime|gcTime|placeholderData|minimumFractionDigits|maximumFractionDigits)$";

// Claves de los mapas de estado (mapa_estados.ts): son los valores
// literales de las columnas `estado`/`resultado` del backend
// (restricciones CHECK en mayusculas, Seccion 6), efectivamente
// "miembros de enumerado" (Seccion 1: UPPER_SNAKE_CASE) aunque el
// objeto en si sea un Record, no un `enum` de TypeScript.
const _CLAVE_TODO_MAYUSCULAS = "^[A-Z][A-Z0-9_]*$";

export default tseslint.config(
  // src/api/tipos_openapi.ts: generado por openapi-typescript a partir del
  // OpenAPI del backend (claves como "/cuentas/{cuenta_id}"). Prohibido
  // tocarlo a mano (Seccion 2.3), asi que tambien queda fuera del lint.
  { ignores: ["dist", "eslint.config.js", "src/api/tipos_openapi.ts"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommendedTypeChecked],
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        project: ["./tsconfig.app.json"],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // `rules-of-hooks` reconoce un hook personalizado solo por su
      // nombre literal (patron `use[A-Z]`, camelCase estricto). La
      // Regla 1 de GUIA_ESTILO_CODIGO.md exige snake_case en espanol
      // para toda funcion propia ("usar_sesion", no "useSesion"), asi
      // que ningun hook de este proyecto puede calzar nunca con ese
      // patron -- no es un caso por caso a silenciar, es una regla
      // fundamentalmente incompatible con la Regla 1. Las Reglas de los
      // Hooks (llamarlos solo en el nivel superior, nunca condicionales)
      // se siguen igual, solo sin verificacion automatica de esta regla
      // puntual. Documentado en DECISIONES.md, Fase 19.
      "react-hooks/rules-of-hooks": "off",
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],

      // GUIA_ESTILO_CODIGO.md, Seccion 1: convencion unica de nombres.
      "@typescript-eslint/naming-convention": [
        "error",
        { selector: "default", format: ["snake_case"], leadingUnderscore: "allow" },
        // PascalCase se permite ademas para los Context de React
        // (`ContextoSesion.Provider` se usa como un componente).
        {
          selector: "variable",
          format: ["snake_case", "UPPER_CASE", "PascalCase"],
          leadingUnderscore: "allow",
        },
        // Componentes React: PascalCase (excepcion impuesta por JSX,
        // Seccion 1). La regla no distingue "componente" de "funcion"
        // por si misma, asi que se permiten ambos formatos aqui.
        { selector: "function", format: ["snake_case", "PascalCase"] },
        {
          selector: "parameter",
          format: ["snake_case"],
          leadingUnderscore: "allow",
          filter: { regex: _PROPIEDADES_EXTERNAS, match: false },
        },
        {
          selector: "parameter",
          format: null,
          filter: { regex: _PROPIEDADES_EXTERNAS, match: true },
        },
        { selector: "typeLike", format: ["PascalCase"] },
        { selector: "enumMember", format: ["UPPER_CASE"] },
        {
          selector: "import",
          format: ["snake_case", "PascalCase", "UPPER_CASE"],
        },
        {
          selector: "objectLiteralProperty",
          format: ["UPPER_CASE"],
          filter: { regex: _CLAVE_TODO_MAYUSCULAS, match: true },
        },
        {
          selector: [
            "property",
            "objectLiteralProperty",
            "typeProperty",
            "objectLiteralMethod",
            "method",
          ],
          format: ["snake_case"],
          leadingUnderscore: "allow",
          filter: { regex: _PROPIEDADES_EXTERNAS, match: false },
        },
        {
          selector: [
            "property",
            "objectLiteralProperty",
            "typeProperty",
            "objectLiteralMethod",
            "method",
          ],
          format: null,
          filter: { regex: _PROPIEDADES_EXTERNAS, match: true },
        },
      ],

      // GUIA_ESTILO_CODIGO.md, Seccion 3: limites de complejidad.
      complexity: ["error", 10],
      "max-lines": ["error", 400],
      "max-lines-per-function": ["error", { max: 50, skipBlankLines: true, skipComments: true }],
      "max-params": ["error", 5],
      "max-depth": ["error", 3],

      // El backend ya expone tipos completos: any manual es casi siempre
      // un tipo generado mal usado, no un borde real con una biblioteca
      // sin tipos (la unica excepcion que permite la Seccion 2.3).
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    },
  },
  {
    files: ["vite.config.ts"],
    extends: [tseslint.configs.disableTypeChecked],
  },
);
