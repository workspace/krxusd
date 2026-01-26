import { Card, CardBody, CardHeader } from "@heroui/react";

export default function Home() {
  return (
    <main className="min-h-screen bg-background p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold text-center mb-8">KRXUSD</h1>
        <p className="text-center text-default-500 mb-12">
          한국 주식을 달러로 확인하세요
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card>
            <CardHeader className="pb-0 pt-4 px-4 flex-col items-start">
              <p className="text-tiny uppercase font-bold">현재 환율</p>
              <h4 className="font-bold text-large">USD/KRW</h4>
            </CardHeader>
            <CardBody className="py-4">
              <p className="text-3xl font-semibold">₩1,450.00</p>
              <p className="text-small text-success">+0.5%</p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader className="pb-0 pt-4 px-4 flex-col items-start">
              <p className="text-tiny uppercase font-bold">KOSPI</p>
              <h4 className="font-bold text-large">종합지수</h4>
            </CardHeader>
            <CardBody className="py-4">
              <p className="text-3xl font-semibold">2,650.00</p>
              <p className="text-small text-default-500">$1.83B</p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader className="pb-0 pt-4 px-4 flex-col items-start">
              <p className="text-tiny uppercase font-bold">KOSDAQ</p>
              <h4 className="font-bold text-large">종합지수</h4>
            </CardHeader>
            <CardBody className="py-4">
              <p className="text-3xl font-semibold">850.00</p>
              <p className="text-small text-default-500">$0.59B</p>
            </CardBody>
          </Card>
        </div>
      </div>
    </main>
  );
}
