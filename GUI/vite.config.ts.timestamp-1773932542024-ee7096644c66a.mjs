// vite.config.ts
import { defineConfig } from "file:///app/node_modules/vite/dist/node/index.js";
import react from "file:///app/node_modules/@vitejs/plugin-react/dist/index.mjs";
import tsconfigPaths from "file:///app/node_modules/vite-tsconfig-paths/dist/index.mjs";
import svgr from "file:///app/node_modules/vite-plugin-svgr/dist/index.mjs";
import path from "path";

// vitePlugin.js
function removeHiddenMenuItems(str) {
  var _a, _b;
  const badJson = str.replace("export default [", "[").replace("];", "]");
  const correctJson = badJson.replace(/(['"])?([a-z0-9A-Z_]+)(['"])?:/g, '"$2": ');
  const isHiddenFeaturesEnabled = ((_a = process.env.REACT_APP_ENABLE_HIDDEN_FEATURES) == null ? void 0 : _a.toLowerCase().trim()) === "true" || ((_b = process.env.REACT_APP_ENABLE_HIDDEN_FEATURES) == null ? void 0 : _b.toLowerCase().trim()) === "1";
  const json = removeHidden(JSON.parse(correctJson), isHiddenFeaturesEnabled);
  const updatedJson = JSON.stringify(json);
  return "export default " + updatedJson + ";";
}
function removeHidden(menuItems, isHiddenFeaturesEnabled) {
  var _a;
  if (!menuItems)
    return menuItems;
  const arr = (_a = menuItems == null ? void 0 : menuItems.filter((x) => !x.hidden)) == null ? void 0 : _a.filter((x) => isHiddenFeaturesEnabled || x.hiddenMode !== "production");
  for (const a of arr) {
    a.children = removeHidden(a.children, isHiddenFeaturesEnabled);
  }
  return arr;
}

// vite.config.ts
var __vite_injected_original_dirname = "/app";
var vite_config_default = defineConfig({
  envPrefix: "REACT_APP_",
  plugins: [
    react(),
    tsconfigPaths(),
    svgr(),
    {
      name: "removeHiddenMenuItemsPlugin",
      transform: (str, id) => {
        if (!id.endsWith("/menu-structure.json"))
          return str;
        return removeHiddenMenuItems(str);
      }
    }
  ],
  base: "/rag-search",
  build: {
    outDir: "./build",
    target: "es2015",
    emptyOutDir: true
  },
  server: {
    headers: {
      ...process.env.REACT_APP_CSP && {
        "Content-Security-Policy": process.env.REACT_APP_CSP
      }
    },
    allowedHosts: ["est-rag-rtc.rootcode.software", "localhost", "127.0.0.1"],
    proxy: {
      "/vault-agent-gui": {
        target: "http://vault-agent-gui:8202",
        changeOrigin: true,
        rewrite: (path2) => path2.replace(/^\/vault-agent-gui/, "")
      }
    }
  },
  resolve: {
    alias: {
      "~@fontsource": path.resolve(__vite_injected_original_dirname, "node_modules/@fontsource"),
      "@": `${path.resolve(__vite_injected_original_dirname, "./src")}`
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiLCAidml0ZVBsdWdpbi5qcyJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiY29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2Rpcm5hbWUgPSBcIi9hcHBcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfZmlsZW5hbWUgPSBcIi9hcHAvdml0ZS5jb25maWcudHNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL2FwcC92aXRlLmNvbmZpZy50c1wiO2ltcG9ydCB7IGRlZmluZUNvbmZpZyB9IGZyb20gJ3ZpdGUnO1xuaW1wb3J0IHJlYWN0IGZyb20gJ0B2aXRlanMvcGx1Z2luLXJlYWN0JztcbmltcG9ydCB0c2NvbmZpZ1BhdGhzIGZyb20gJ3ZpdGUtdHNjb25maWctcGF0aHMnO1xuaW1wb3J0IHN2Z3IgZnJvbSAndml0ZS1wbHVnaW4tc3Zncic7XG5pbXBvcnQgcGF0aCBmcm9tICdwYXRoJztcbmltcG9ydCB7IHJlbW92ZUhpZGRlbk1lbnVJdGVtcyB9IGZyb20gJy4vdml0ZVBsdWdpbic7XG5cbi8vIGh0dHBzOi8vdml0ZWpzLmRldi9jb25maWcvXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoe1xuICBlbnZQcmVmaXg6ICdSRUFDVF9BUFBfJyxcbiAgcGx1Z2luczogW1xuICAgIHJlYWN0KCksXG4gICAgdHNjb25maWdQYXRocygpLFxuICAgIHN2Z3IoKSxcbiAgICB7XG4gICAgICBuYW1lOiAncmVtb3ZlSGlkZGVuTWVudUl0ZW1zUGx1Z2luJyxcbiAgICAgIHRyYW5zZm9ybTogKHN0ciwgaWQpID0+IHtcbiAgICAgICAgaWYoIWlkLmVuZHNXaXRoKCcvbWVudS1zdHJ1Y3R1cmUuanNvbicpKVxuICAgICAgICAgIHJldHVybiBzdHI7XG4gICAgICAgIHJldHVybiByZW1vdmVIaWRkZW5NZW51SXRlbXMoc3RyKTtcbiAgICAgIH0sXG4gICAgfSxcbiAgXSxcbiAgYmFzZTogJy9yYWctc2VhcmNoJyxcbiAgYnVpbGQ6IHtcbiAgICBvdXREaXI6ICcuL2J1aWxkJyxcbiAgICB0YXJnZXQ6ICdlczIwMTUnLFxuICAgIGVtcHR5T3V0RGlyOiB0cnVlLFxuICB9LFxuICBzZXJ2ZXI6IHtcbiAgICBoZWFkZXJzOiB7XG4gICAgICAuLi4ocHJvY2Vzcy5lbnYuUkVBQ1RfQVBQX0NTUCAmJiB7XG4gICAgICAgICdDb250ZW50LVNlY3VyaXR5LVBvbGljeSc6IHByb2Nlc3MuZW52LlJFQUNUX0FQUF9DU1AsXG4gICAgICB9KSxcbiAgICB9LFxuICAgIGFsbG93ZWRIb3N0czogWydlc3QtcmFnLXJ0Yy5yb290Y29kZS5zb2Z0d2FyZScsICdsb2NhbGhvc3QnLCAnMTI3LjAuMC4xJ10sXG4gICAgcHJveHk6IHtcbiAgICAgICcvdmF1bHQtYWdlbnQtZ3VpJzoge1xuICAgICAgICB0YXJnZXQ6ICdodHRwOi8vdmF1bHQtYWdlbnQtZ3VpOjgyMDInLFxuICAgICAgICBjaGFuZ2VPcmlnaW46IHRydWUsXG4gICAgICAgIHJld3JpdGU6IChwYXRoKSA9PiBwYXRoLnJlcGxhY2UoL15cXC92YXVsdC1hZ2VudC1ndWkvLCAnJyksXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIHJlc29sdmU6IHtcbiAgICBhbGlhczoge1xuICAgICAgJ35AZm9udHNvdXJjZSc6IHBhdGgucmVzb2x2ZShfX2Rpcm5hbWUsICdub2RlX21vZHVsZXMvQGZvbnRzb3VyY2UnKSxcbiAgICAgICdAJzogYCR7cGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgJy4vc3JjJyl9YCxcbiAgICB9LFxuICB9LFxufSk7XG4iLCAiY29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2Rpcm5hbWUgPSBcIi9hcHBcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfZmlsZW5hbWUgPSBcIi9hcHAvdml0ZVBsdWdpbi5qc1wiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9pbXBvcnRfbWV0YV91cmwgPSBcImZpbGU6Ly8vYXBwL3ZpdGVQbHVnaW4uanNcIjtleHBvcnQgZnVuY3Rpb24gcmVtb3ZlSGlkZGVuTWVudUl0ZW1zKHN0cikge1xuICBjb25zdCBiYWRKc29uID0gc3RyLnJlcGxhY2UoJ2V4cG9ydCBkZWZhdWx0IFsnLCAnWycpLnJlcGxhY2UoJ107JywgJ10nKTtcbiAgY29uc3QgY29ycmVjdEpzb24gPSBiYWRKc29uLnJlcGxhY2UoLyhbJ1wiXSk/KFthLXowLTlBLVpfXSspKFsnXCJdKT86L2csICdcIiQyXCI6ICcpO1xuXG4gY29uc3QgaXNIaWRkZW5GZWF0dXJlc0VuYWJsZWQgPSBcbiAgICBwcm9jZXNzLmVudi5SRUFDVF9BUFBfRU5BQkxFX0hJRERFTl9GRUFUVVJFUz8udG9Mb3dlckNhc2UoKS50cmltKCkgPT09ICd0cnVlJyB8fFxuICAgIHByb2Nlc3MuZW52LlJFQUNUX0FQUF9FTkFCTEVfSElEREVOX0ZFQVRVUkVTPy50b0xvd2VyQ2FzZSgpLnRyaW0oKSA9PT0gJzEnO1xuXG4gIGNvbnN0IGpzb24gPSByZW1vdmVIaWRkZW4oSlNPTi5wYXJzZShjb3JyZWN0SnNvbiksIGlzSGlkZGVuRmVhdHVyZXNFbmFibGVkKTtcbiAgXG4gIGNvbnN0IHVwZGF0ZWRKc29uID0gSlNPTi5zdHJpbmdpZnkoanNvbik7XG5cbiAgcmV0dXJuICdleHBvcnQgZGVmYXVsdCAnICsgdXBkYXRlZEpzb24gKyAnOydcbn1cblxuZnVuY3Rpb24gcmVtb3ZlSGlkZGVuKG1lbnVJdGVtcywgaXNIaWRkZW5GZWF0dXJlc0VuYWJsZWQpIHtcbiAgaWYoIW1lbnVJdGVtcykgcmV0dXJuIG1lbnVJdGVtcztcbiAgY29uc3QgYXJyID0gbWVudUl0ZW1zXG4gICAgPy5maWx0ZXIoeCA9PiAheC5oaWRkZW4pXG4gICAgPy5maWx0ZXIoeCA9PiBpc0hpZGRlbkZlYXR1cmVzRW5hYmxlZCB8fCB4LmhpZGRlbk1vZGUgIT09IFwicHJvZHVjdGlvblwiKTtcbiAgZm9yIChjb25zdCBhIG9mIGFycikge1xuICAgIGEuY2hpbGRyZW4gPSByZW1vdmVIaWRkZW4oYS5jaGlsZHJlbiwgaXNIaWRkZW5GZWF0dXJlc0VuYWJsZWQpO1xuICB9XG4gIHJldHVybiBhcnI7XG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBQThMLFNBQVMsb0JBQW9CO0FBQzNOLE9BQU8sV0FBVztBQUNsQixPQUFPLG1CQUFtQjtBQUMxQixPQUFPLFVBQVU7QUFDakIsT0FBTyxVQUFVOzs7QUNKa0wsU0FBUyxzQkFBc0IsS0FBSztBQUF2TztBQUNFLFFBQU0sVUFBVSxJQUFJLFFBQVEsb0JBQW9CLEdBQUcsRUFBRSxRQUFRLE1BQU0sR0FBRztBQUN0RSxRQUFNLGNBQWMsUUFBUSxRQUFRLG1DQUFtQyxRQUFRO0FBRWhGLFFBQU0sNEJBQ0gsYUFBUSxJQUFJLHFDQUFaLG1CQUE4QyxjQUFjLFlBQVcsWUFDdkUsYUFBUSxJQUFJLHFDQUFaLG1CQUE4QyxjQUFjLFlBQVc7QUFFekUsUUFBTSxPQUFPLGFBQWEsS0FBSyxNQUFNLFdBQVcsR0FBRyx1QkFBdUI7QUFFMUUsUUFBTSxjQUFjLEtBQUssVUFBVSxJQUFJO0FBRXZDLFNBQU8sb0JBQW9CLGNBQWM7QUFDM0M7QUFFQSxTQUFTLGFBQWEsV0FBVyx5QkFBeUI7QUFmMUQ7QUFnQkUsTUFBRyxDQUFDO0FBQVcsV0FBTztBQUN0QixRQUFNLE9BQU0sNENBQ1IsT0FBTyxPQUFLLENBQUMsRUFBRSxZQURQLG1CQUVSLE9BQU8sT0FBSywyQkFBMkIsRUFBRSxlQUFlO0FBQzVELGFBQVcsS0FBSyxLQUFLO0FBQ25CLE1BQUUsV0FBVyxhQUFhLEVBQUUsVUFBVSx1QkFBdUI7QUFBQSxFQUMvRDtBQUNBLFNBQU87QUFDVDs7O0FEeEJBLElBQU0sbUNBQW1DO0FBUXpDLElBQU8sc0JBQVEsYUFBYTtBQUFBLEVBQzFCLFdBQVc7QUFBQSxFQUNYLFNBQVM7QUFBQSxJQUNQLE1BQU07QUFBQSxJQUNOLGNBQWM7QUFBQSxJQUNkLEtBQUs7QUFBQSxJQUNMO0FBQUEsTUFDRSxNQUFNO0FBQUEsTUFDTixXQUFXLENBQUMsS0FBSyxPQUFPO0FBQ3RCLFlBQUcsQ0FBQyxHQUFHLFNBQVMsc0JBQXNCO0FBQ3BDLGlCQUFPO0FBQ1QsZUFBTyxzQkFBc0IsR0FBRztBQUFBLE1BQ2xDO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLE1BQU07QUFBQSxFQUNOLE9BQU87QUFBQSxJQUNMLFFBQVE7QUFBQSxJQUNSLFFBQVE7QUFBQSxJQUNSLGFBQWE7QUFBQSxFQUNmO0FBQUEsRUFDQSxRQUFRO0FBQUEsSUFDTixTQUFTO0FBQUEsTUFDUCxHQUFJLFFBQVEsSUFBSSxpQkFBaUI7QUFBQSxRQUMvQiwyQkFBMkIsUUFBUSxJQUFJO0FBQUEsTUFDekM7QUFBQSxJQUNGO0FBQUEsSUFDQSxjQUFjLENBQUMsaUNBQWlDLGFBQWEsV0FBVztBQUFBLElBQ3hFLE9BQU87QUFBQSxNQUNMLG9CQUFvQjtBQUFBLFFBQ2xCLFFBQVE7QUFBQSxRQUNSLGNBQWM7QUFBQSxRQUNkLFNBQVMsQ0FBQ0EsVUFBU0EsTUFBSyxRQUFRLHNCQUFzQixFQUFFO0FBQUEsTUFDMUQ7QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUFBLEVBQ0EsU0FBUztBQUFBLElBQ1AsT0FBTztBQUFBLE1BQ0wsZ0JBQWdCLEtBQUssUUFBUSxrQ0FBVywwQkFBMEI7QUFBQSxNQUNsRSxLQUFLLEdBQUcsS0FBSyxRQUFRLGtDQUFXLE9BQU8sQ0FBQztBQUFBLElBQzFDO0FBQUEsRUFDRjtBQUNGLENBQUM7IiwKICAibmFtZXMiOiBbInBhdGgiXQp9Cg==
