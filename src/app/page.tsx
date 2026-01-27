"use client";

import { Divider } from "@heroui/react";
import {
  ExchangeRateCard,
  KospiIndexCard,
  KosdaqIndexCard,
  PopularStocksList,
  MarketStatusBadge,
} from "@/components";

export default function Home() {
  return (
    <main className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-background/80 backdrop-blur-lg border-b border-divider">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                KRXUSD
              </h1>
              <p className="text-small text-default-500 mt-1">
                Korean Stocks in USD - Real-time Price Tracking
              </p>
            </div>
            <MarketStatusBadge />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {/* Hero Section - Exchange Rate & Market Indices */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-default-700 mb-4">
            Market Overview
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
            <ExchangeRateCard />
            <KospiIndexCard />
            <KosdaqIndexCard />
          </div>
        </section>

        <Divider className="my-6 sm:my-8" />

        {/* Popular Stocks Section */}
        <section>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="lg:col-span-2">
              <PopularStocksList />
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="mt-12 pt-6 border-t border-divider">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-small text-default-400">
            <p>
              Data provided for informational purposes only. Not financial advice.
            </p>
            <p>
              Sources: FinanceDataReader, Yahoo Finance
            </p>
          </div>
        </footer>
      </div>
    </main>
  );
}
