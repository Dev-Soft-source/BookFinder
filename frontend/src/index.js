import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import favicon from "@/assets/book_scout.png";

const link = document.createElement("link");
link.rel = "icon";
link.type = "image/png";
link.href = favicon;
document.head.appendChild(link);

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
