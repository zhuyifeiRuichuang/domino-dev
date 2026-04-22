import { Button, type ButtonProps } from "@mui/material";
import React, { useEffect, useRef } from "react";
import { useReactToPrint } from "react-to-print";

interface Props extends ButtonProps {
  contentId: string;
}

export const DownloadAsPDF: React.FC<Props> = ({ contentId, ...props }) => {
  const contentRef = useRef<HTMLElement | null>(null);

  const handlePrint = useReactToPrint({
    contentRef,
  });

  useEffect(() => {
    contentRef.current = document.getElementById(contentId);
  }, [contentId]);

  const handlePrintWithTimeout = () => {
    // Add a short timeout to ensure styles are applied before printing
    setTimeout(() => {
      handlePrint();
    }, 2000); // Adjust the timeout duration as needed
  };

  return (
    <Button variant="outlined" onClick={handlePrintWithTimeout} {...props}>
      Generate PDF
    </Button>
  );
};
