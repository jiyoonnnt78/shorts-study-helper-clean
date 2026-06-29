import Link from "next/link";
import BrandHeader from "@/components/BrandHeader";

export const metadata = {
  title: "개인정보처리방침 | 쇼츠 공부 도우미",
};

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-6">
      <h2 className="font-display text-lg text-ink mb-2">{title}</h2>
      <div className="space-y-2 text-sm leading-relaxed text-ink/80">
        {children}
      </div>
    </section>
  );
}

function Table({
  head,
  rows,
}: {
  head: string[];
  rows: string[][];
}) {
  return (
    <div className="overflow-x-auto rounded-2xl ring-1 ring-black/10 my-3">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-blueberry text-white">
            {head.map((h) => (
              <th key={h} className="px-3 py-2 text-left font-display">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="odd:bg-white even:bg-sunshine-soft/30">
              {r.map((c, j) => (
                <td key={j} className="px-3 py-2 align-top text-ink/80">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <>
      <BrandHeader compact />
      <main className="flex flex-1 flex-col gap-4 pb-12">
        <div className="text-center mb-4">
          <h1 className="font-display text-2xl text-ink">
            개인정보처리방침
          </h1>
          <p className="mt-1 text-sm text-ink/50">시행일: 2026년 6월 29일</p>
        </div>

        <p className="text-sm leading-relaxed text-ink/80">
          &ldquo;쇼츠 공부 도우미&rdquo;(이하 &ldquo;서비스&rdquo;)는 초등학생
          대상 숏폼 영상 분석 교육 도구로, 이용자의 개인정보를 다음과 같이
          처리합니다.
        </p>

        <Section title="제1조 (수집하는 개인정보 항목 및 수집 방법)">
          <p>
            본 서비스는 회원가입 절차가 없으며, 이름·이메일·전화번호 등
            신원을 식별할 수 있는 정보를 별도로 수집하지 않습니다. 서비스
            이용 과정에서 다음 정보만 처리됩니다.
          </p>
          <Table
            head={["구분", "수집 항목", "수집 방법"]}
            rows={[
              [
                "유튜브 링크 분석",
                "입력한 유튜브 영상 URL, 해당 영상의 공개된 제목·설명·썸네일·해시태그",
                "이용자 입력 + 유튜브 공개 API",
              ],
              ["영상 파일 업로드(선택)", "업로드한 영상 파일 자체", "이용자 업로드"],
              [
                "서비스 이용 기록",
                "접속 IP, 접속 시각, 오류 로그(서버 운영용)",
                "자동 수집",
              ],
            ]}
          />
          <p>
            업로드 영상에는 촬영자·출연자의 얼굴, 음성 등이 포함될 수
            있습니다. 서비스는 영상 속 인물을 식별하거나 별도로
            저장·활용하지 않으며, 영상은 아래 제3조의 보관 기간 동안 분석
            목적으로만 사용됩니다.
          </p>
        </Section>

        <Section title="제2조 (개인정보의 수집 및 이용 목적)">
          <ul className="list-disc pl-5 space-y-1">
            <li>입력한 영상 URL/업로드 영상을 분석하여 영상 구조·훅 분석 결과를 제공</li>
            <li>서비스 안정적 운영, 오류 확인 및 개선</li>
            <li>부정 이용 방지(과도한 반복 요청 차단 등)</li>
          </ul>
          <p>
            수집된 정보는 위 목적 외에는 이용하지 않으며, 광고·마케팅에
            활용하지 않습니다.
          </p>
        </Section>

        <Section title="제3조 (개인정보의 보유 및 이용 기간)">
          <ul className="list-disc pl-5 space-y-1">
            <li>
              업로드 영상 파일 및 추출된 화면 캡처:{" "}
              <b>분석 완료 후 최대 14일간</b> 서버에 보관되며, 이후 자동
              삭제됩니다. 이용자가 직접 &ldquo;결과 지우기&rdquo;를 누르면
              즉시 삭제됩니다.
            </li>
            <li>
              분석 결과 텍스트(요약·구조 분석 등): 서비스 운영을 위해 별도
              삭제 요청 전까지 보관되나, 특정 개인을 식별할 수 있는 정보는
              포함하지 않습니다.
            </li>
            <li>서버 접속/오류 로그: 최대 30일간 보관 후 자동 삭제됩니다.</li>
          </ul>
        </Section>

        <Section title="제4조 (개인정보의 제3자 제공)">
          <p>
            서비스는 이용자의 정보를 외부에 판매하거나 제공하지 않습니다.
            단, 서비스 제공을 위해 다음 항목이 분석 과정에서 일시적으로
            전송됩니다.
          </p>
          <Table
            head={["제공받는 자", "제공 목적", "제공 항목", "보유 기간"]}
            rows={[
              [
                "OpenAI(분석 엔진)",
                "영상 장면 분석을 위한 AI 처리",
                "영상에서 추출한 화면 캡처(저해상도), 제목/설명 텍스트",
                "OpenAI 자체 정책에 따름(자체 저장 안 함)",
              ],
            ]}
          />
          <p>
            위 항목은 분석 1회 처리를 위해서만 전송되며, 별도로 영구
            저장되지 않습니다.
          </p>
        </Section>

        <Section title="제5조 (개인정보 처리의 위탁)">
          <p>서비스 운영을 위해 다음과 같이 개인정보 처리 업무를 위탁하고 있습니다.</p>
          <Table
            head={["수탁업체", "위탁업무 내용"]}
            rows={[
              ["Render (render.com)", "백엔드 서버 호스팅, 데이터베이스(PostgreSQL) 운영"],
              ["Vercel (vercel.com)", "프론트엔드(웹페이지) 호스팅"],
              ["RapidAPI 제휴사", "입력된 유튜브 링크의 영상 파일 가져오기(다운로드)"],
              ["OpenAI", "영상 장면 AI 분석"],
            ]}
          />
          <p>
            수탁업체는 위탁 목적 범위 내에서만 정보를 처리하며, 목적 외
            이용을 금지하고 있습니다.
          </p>
        </Section>

        <Section title="제6조 (이용자의 권리와 행사 방법)">
          <p>이용자는 언제든지 다음 권리를 행사할 수 있습니다.</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              본인이 업로드한 영상 및 분석 결과의 열람·삭제: 결과 페이지의
              &ldquo;이 결과 지우기&rdquo; 버튼 또는 하단 문의처로 요청
            </li>
            <li>분석 처리의 중단 요청: 문의처로 연락 시 즉시 처리</li>
          </ul>
          <p>
            만 14세 미만 학생이 서비스를 이용하는 경우, 수업을 진행하는
            교사의 지도 및 책임 하에 이용하는 것을 전제로 하며, 학생 개인을
            식별하는 정보(이름, 학번 등)는 입력하지 않도록 안내하고
            있습니다. 보호자 또는 교사는 학생을 대신하여 위 권리를 행사할
            수 있습니다.
          </p>
        </Section>

        <Section title="제7조 (개인정보의 안전성 확보 조치)">
          <ul className="list-disc pl-5 space-y-1">
            <li>서버(Render)와 호스팅(Vercel) 간 통신은 HTTPS로 암호화됩니다.</li>
            <li>
              업로드 파일은 추측이 어려운 임의 식별자로 저장되며, 직접 URL
              추측을 통한 접근을 차단합니다.
            </li>
            <li>접근 권한은 서비스 운영자(개발 담당 교사)로 제한됩니다.</li>
            <li>별도의 결제 정보, 주민등록번호 등 고유식별정보는 수집하지 않습니다.</li>
          </ul>
        </Section>

        <Section title="제8조 (개인정보 보호책임자)">
          <Table
            head={["구분", "내용"]}
            rows={[
              ["성명", "박지윤"],
              ["소속", "인천동암초등학교"],
              ["이메일", "(문의처 이메일을 입력하세요)"],
            ]}
          />
          <p>
            개인정보 처리에 관한 문의, 불만 처리, 피해 구제 등에 관한 사항은
            위 연락처로 문의하실 수 있습니다.
          </p>
        </Section>

        <Section title="제9조 (적용 범위)">
          <p>
            본 서비스는 인천동암초등학교 외에도 본 서비스의 교육적 취지에
            동의하는 다른 학교·교사가 자유롭게 이용할 수 있도록 공개되어
            있으며, 본 처리방침은 서비스를 이용하는 모든 이용자에게 동일하게
            적용됩니다.
          </p>
        </Section>

        <Section title="부칙">
          <p>
            본 처리방침은 2026년 6월 29일부터 시행됩니다. 내용 변경 시
            서비스 내 공지 또는 본 문서 갱신을 통해 안내합니다.
          </p>
        </Section>

        <div className="mt-4 text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-full bg-white px-5 py-2.5 text-sm font-bold text-ink/60 ring-1 ring-black/10 transition-colors hover:bg-blueberry-soft hover:text-blueberry"
          >
            ← 홈으로 돌아가기
          </Link>
        </div>
      </main>
    </>
  );
}
