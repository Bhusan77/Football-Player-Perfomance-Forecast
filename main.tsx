// Entry point for the standalone Data Scout bundle.
// Mounts the *exact* Day 5 course lab (ScoutBuilderLab) — same components,
// same features — which talk to the local server's /api/data-scout endpoint.
import React from "react";
import { createRoot } from "react-dom/client";
import ScoutBuilderLab from "@/components/ScoutBuilderLab";

const el = document.getElementById("root");
if (el) createRoot(el).render(<ScoutBuilderLab />);
