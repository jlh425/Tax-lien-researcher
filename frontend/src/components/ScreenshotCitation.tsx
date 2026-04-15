import { useState } from "react";

interface Props {
  /** Base64-encoded image data or URL to the cropped screenshot. */
  imageUrl: string;
  /** URL of the original page the screenshot was taken from. */
  sourceUrl: string;
  /** Date the screenshot was captured. */
  retrievedAt: string;
  /** Alt text for accessibility. */
  alt?: string;
}

export function ScreenshotCitation({ imageUrl, sourceUrl, retrievedAt, alt }: Props) {
  const [showModal, setShowModal] = useState(false);

  const formattedDate = new Date(retrievedAt).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <>
      <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
        {/* Cropped screenshot region */}
        <button
          onClick={() => setShowModal(true)}
          className="w-full cursor-pointer hover:opacity-90 transition"
        >
          <img
            src={imageUrl}
            alt={alt ?? "Screenshot citation"}
            className="w-full h-auto max-h-48 object-cover"
          />
        </button>

        {/* Citation footer */}
        <div className="px-3 py-2 flex items-center justify-between gap-2 bg-gray-50 border-t border-gray-100">
          <span className="text-xs text-gray-400">
            Retrieved {formattedDate}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setShowModal(true)}
              className="text-xs text-blue-500 hover:text-blue-700 transition"
            >
              View full page
            </button>
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-500 hover:text-blue-700 transition"
            >
              Open source URL
            </a>
          </div>
        </div>
      </div>

      {/* Full-page modal */}
      {showModal && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          onClick={() => setShowModal(false)}
        >
          <div
            className="bg-white rounded-lg shadow-2xl max-w-5xl max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
              <span className="text-sm font-medium text-gray-700">
                Screenshot — {formattedDate}
              </span>
              <div className="flex items-center gap-3">
                <a
                  href={sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-500 hover:text-blue-700"
                >
                  Open source URL
                </a>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-gray-600 text-lg leading-none"
                >
                  &times;
                </button>
              </div>
            </div>
            <img
              src={imageUrl}
              alt={alt ?? "Full page screenshot"}
              className="w-full h-auto"
            />
          </div>
        </div>
      )}
    </>
  );
}
