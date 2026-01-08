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
    allowedHosts: ["est-rag-rtc.rootcode.software", "localhost", "127.0.0.1"]
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
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiLCAidml0ZVBsdWdpbi5qcyJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiY29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2Rpcm5hbWUgPSBcIi9hcHBcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfZmlsZW5hbWUgPSBcIi9hcHAvdml0ZS5jb25maWcudHNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL2FwcC92aXRlLmNvbmZpZy50c1wiO2ltcG9ydCB7IGRlZmluZUNvbmZpZyB9IGZyb20gJ3ZpdGUnO1xuaW1wb3J0IHJlYWN0IGZyb20gJ0B2aXRlanMvcGx1Z2luLXJlYWN0JztcbmltcG9ydCB0c2NvbmZpZ1BhdGhzIGZyb20gJ3ZpdGUtdHNjb25maWctcGF0aHMnO1xuaW1wb3J0IHN2Z3IgZnJvbSAndml0ZS1wbHVnaW4tc3Zncic7XG5pbXBvcnQgcGF0aCBmcm9tICdwYXRoJztcbmltcG9ydCB7IHJlbW92ZUhpZGRlbk1lbnVJdGVtcyB9IGZyb20gJy4vdml0ZVBsdWdpbic7XG5cbi8vIGh0dHBzOi8vdml0ZWpzLmRldi9jb25maWcvXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoe1xuICBlbnZQcmVmaXg6ICdSRUFDVF9BUFBfJyxcbiAgcGx1Z2luczogW1xuICAgIHJlYWN0KCksXG4gICAgdHNjb25maWdQYXRocygpLFxuICAgIHN2Z3IoKSxcbiAgICB7XG4gICAgICBuYW1lOiAncmVtb3ZlSGlkZGVuTWVudUl0ZW1zUGx1Z2luJyxcbiAgICAgIHRyYW5zZm9ybTogKHN0ciwgaWQpID0+IHtcbiAgICAgICAgaWYoIWlkLmVuZHNXaXRoKCcvbWVudS1zdHJ1Y3R1cmUuanNvbicpKVxuICAgICAgICAgIHJldHVybiBzdHI7XG4gICAgICAgIHJldHVybiByZW1vdmVIaWRkZW5NZW51SXRlbXMoc3RyKTtcbiAgICAgIH0sXG4gICAgfSxcbiAgXSxcbiAgYmFzZTogJy9yYWctc2VhcmNoJyxcbiAgYnVpbGQ6IHtcbiAgICBvdXREaXI6ICcuL2J1aWxkJyxcbiAgICB0YXJnZXQ6ICdlczIwMTUnLFxuICAgIGVtcHR5T3V0RGlyOiB0cnVlLFxuICB9LFxuICBzZXJ2ZXI6IHtcbiAgICBoZWFkZXJzOiB7XG4gICAgICAuLi4ocHJvY2Vzcy5lbnYuUkVBQ1RfQVBQX0NTUCAmJiB7XG4gICAgICAgICdDb250ZW50LVNlY3VyaXR5LVBvbGljeSc6IHByb2Nlc3MuZW52LlJFQUNUX0FQUF9DU1AsXG4gICAgICB9KSxcbiAgICB9LFxuICAgIGFsbG93ZWRIb3N0czogWydlc3QtcmFnLXJ0Yy5yb290Y29kZS5zb2Z0d2FyZScsICdsb2NhbGhvc3QnLCAnMTI3LjAuMC4xJ10sXG5cbiAgfSxcbiAgcmVzb2x2ZToge1xuICAgIGFsaWFzOiB7XG4gICAgICAnfkBmb250c291cmNlJzogcGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgJ25vZGVfbW9kdWxlcy9AZm9udHNvdXJjZScpLFxuICAgICAgJ0AnOiBgJHtwYXRoLnJlc29sdmUoX19kaXJuYW1lLCAnLi9zcmMnKX1gLFxuICAgIH0sXG4gIH0sXG59KTtcbiIsICJjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfZGlybmFtZSA9IFwiL2FwcFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiL2FwcC92aXRlUGx1Z2luLmpzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9hcHAvdml0ZVBsdWdpbi5qc1wiO2V4cG9ydCBmdW5jdGlvbiByZW1vdmVIaWRkZW5NZW51SXRlbXMoc3RyKSB7XG4gIGNvbnN0IGJhZEpzb24gPSBzdHIucmVwbGFjZSgnZXhwb3J0IGRlZmF1bHQgWycsICdbJykucmVwbGFjZSgnXTsnLCAnXScpO1xuICBjb25zdCBjb3JyZWN0SnNvbiA9IGJhZEpzb24ucmVwbGFjZSgvKFsnXCJdKT8oW2EtejAtOUEtWl9dKykoWydcIl0pPzovZywgJ1wiJDJcIjogJyk7XG5cbiBjb25zdCBpc0hpZGRlbkZlYXR1cmVzRW5hYmxlZCA9IFxuICAgIHByb2Nlc3MuZW52LlJFQUNUX0FQUF9FTkFCTEVfSElEREVOX0ZFQVRVUkVTPy50b0xvd2VyQ2FzZSgpLnRyaW0oKSA9PT0gJ3RydWUnIHx8XG4gICAgcHJvY2Vzcy5lbnYuUkVBQ1RfQVBQX0VOQUJMRV9ISURERU5fRkVBVFVSRVM/LnRvTG93ZXJDYXNlKCkudHJpbSgpID09PSAnMSc7XG5cbiAgY29uc3QganNvbiA9IHJlbW92ZUhpZGRlbihKU09OLnBhcnNlKGNvcnJlY3RKc29uKSwgaXNIaWRkZW5GZWF0dXJlc0VuYWJsZWQpO1xuICBcbiAgY29uc3QgdXBkYXRlZEpzb24gPSBKU09OLnN0cmluZ2lmeShqc29uKTtcblxuICByZXR1cm4gJ2V4cG9ydCBkZWZhdWx0ICcgKyB1cGRhdGVkSnNvbiArICc7J1xufVxuXG5mdW5jdGlvbiByZW1vdmVIaWRkZW4obWVudUl0ZW1zLCBpc0hpZGRlbkZlYXR1cmVzRW5hYmxlZCkge1xuICBpZighbWVudUl0ZW1zKSByZXR1cm4gbWVudUl0ZW1zO1xuICBjb25zdCBhcnIgPSBtZW51SXRlbXNcbiAgICA/LmZpbHRlcih4ID0+ICF4LmhpZGRlbilcbiAgICA/LmZpbHRlcih4ID0+IGlzSGlkZGVuRmVhdHVyZXNFbmFibGVkIHx8IHguaGlkZGVuTW9kZSAhPT0gXCJwcm9kdWN0aW9uXCIpO1xuICBmb3IgKGNvbnN0IGEgb2YgYXJyKSB7XG4gICAgYS5jaGlsZHJlbiA9IHJlbW92ZUhpZGRlbihhLmNoaWxkcmVuLCBpc0hpZGRlbkZlYXR1cmVzRW5hYmxlZCk7XG4gIH1cbiAgcmV0dXJuIGFycjtcbn1cbiJdLAogICJtYXBwaW5ncyI6ICI7QUFBOEwsU0FBUyxvQkFBb0I7QUFDM04sT0FBTyxXQUFXO0FBQ2xCLE9BQU8sbUJBQW1CO0FBQzFCLE9BQU8sVUFBVTtBQUNqQixPQUFPLFVBQVU7OztBQ0prTCxTQUFTLHNCQUFzQixLQUFLO0FBQXZPO0FBQ0UsUUFBTSxVQUFVLElBQUksUUFBUSxvQkFBb0IsR0FBRyxFQUFFLFFBQVEsTUFBTSxHQUFHO0FBQ3RFLFFBQU0sY0FBYyxRQUFRLFFBQVEsbUNBQW1DLFFBQVE7QUFFaEYsUUFBTSw0QkFDSCxhQUFRLElBQUkscUNBQVosbUJBQThDLGNBQWMsWUFBVyxZQUN2RSxhQUFRLElBQUkscUNBQVosbUJBQThDLGNBQWMsWUFBVztBQUV6RSxRQUFNLE9BQU8sYUFBYSxLQUFLLE1BQU0sV0FBVyxHQUFHLHVCQUF1QjtBQUUxRSxRQUFNLGNBQWMsS0FBSyxVQUFVLElBQUk7QUFFdkMsU0FBTyxvQkFBb0IsY0FBYztBQUMzQztBQUVBLFNBQVMsYUFBYSxXQUFXLHlCQUF5QjtBQWYxRDtBQWdCRSxNQUFHLENBQUM7QUFBVyxXQUFPO0FBQ3RCLFFBQU0sT0FBTSw0Q0FDUixPQUFPLE9BQUssQ0FBQyxFQUFFLFlBRFAsbUJBRVIsT0FBTyxPQUFLLDJCQUEyQixFQUFFLGVBQWU7QUFDNUQsYUFBVyxLQUFLLEtBQUs7QUFDbkIsTUFBRSxXQUFXLGFBQWEsRUFBRSxVQUFVLHVCQUF1QjtBQUFBLEVBQy9EO0FBQ0EsU0FBTztBQUNUOzs7QUR4QkEsSUFBTSxtQ0FBbUM7QUFRekMsSUFBTyxzQkFBUSxhQUFhO0FBQUEsRUFDMUIsV0FBVztBQUFBLEVBQ1gsU0FBUztBQUFBLElBQ1AsTUFBTTtBQUFBLElBQ04sY0FBYztBQUFBLElBQ2QsS0FBSztBQUFBLElBQ0w7QUFBQSxNQUNFLE1BQU07QUFBQSxNQUNOLFdBQVcsQ0FBQyxLQUFLLE9BQU87QUFDdEIsWUFBRyxDQUFDLEdBQUcsU0FBUyxzQkFBc0I7QUFDcEMsaUJBQU87QUFDVCxlQUFPLHNCQUFzQixHQUFHO0FBQUEsTUFDbEM7QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUFBLEVBQ0EsTUFBTTtBQUFBLEVBQ04sT0FBTztBQUFBLElBQ0wsUUFBUTtBQUFBLElBQ1IsUUFBUTtBQUFBLElBQ1IsYUFBYTtBQUFBLEVBQ2Y7QUFBQSxFQUNBLFFBQVE7QUFBQSxJQUNOLFNBQVM7QUFBQSxNQUNQLEdBQUksUUFBUSxJQUFJLGlCQUFpQjtBQUFBLFFBQy9CLDJCQUEyQixRQUFRLElBQUk7QUFBQSxNQUN6QztBQUFBLElBQ0Y7QUFBQSxJQUNBLGNBQWMsQ0FBQyxpQ0FBaUMsYUFBYSxXQUFXO0FBQUEsRUFFMUU7QUFBQSxFQUNBLFNBQVM7QUFBQSxJQUNQLE9BQU87QUFBQSxNQUNMLGdCQUFnQixLQUFLLFFBQVEsa0NBQVcsMEJBQTBCO0FBQUEsTUFDbEUsS0FBSyxHQUFHLEtBQUssUUFBUSxrQ0FBVyxPQUFPLENBQUM7QUFBQSxJQUMxQztBQUFBLEVBQ0Y7QUFDRixDQUFDOyIsCiAgIm5hbWVzIjogW10KfQo=
